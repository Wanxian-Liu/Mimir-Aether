#!/usr/bin/env python3
"""
Belief callback for capsule TaskLoop — LLM-driven Predict-then-Attribute.

Gap Analysis #1: 原版 Arm 4 搜索效率 ×4 (1.405→1.349, 26轮→保持)
我们的 _compress_lesson 只输出 "有效: {hypothesis}" — 没有归因。

两级实现:
  - ENHANCED (默认): 模式分析 — 检测趋势/饱和/方向切换，无需 API
  - LLM (可选): 真正的 Predict-then-Attribute — 需要 OPENAI_API_KEY 或
    OPENAI_BASE_URL + OPENAI_API_KEY

用法:
  from scripts.belief_capsule import make_belief_callback
  callback = make_belief_callback()  # 自动选择可用模式
"""

import os
import re
from collections import defaultdict


# ============================================================
# ENHANCED: 模式分析 (零 API)
# ============================================================

def _analyze_patterns(all_rounds_data: list[dict]) -> str:
    """分析多轮结果的模式 — 比 _compress_lesson 丰富得多。

    all_rounds_data: [{"round": N, "hypothesis": "...", "delta": ±X, "passed": T/F}, ...]
    """
    if not all_rounds_data:
        return ""

    passed = [r for r in all_rounds_data if r["passed"] and r["delta"] > 0.001]
    failed = [r for r in all_rounds_data if not r["passed"]]

    beliefs = []

    # 1. 趋势检测
    if len(passed) >= 3:
        deltas = [r["delta"] for r in passed[-5:]]
        recent_avg = sum(deltas[-3:]) / max(len(deltas[-3:]), 1)
        early_avg = sum(deltas[:3]) / max(len(deltas[:3]), 1)

        if recent_avg < early_avg * 0.3:
            beliefs.append(f"接近饱和: 最近3轮 Δ_avg={recent_avg:.4f} 远低于早期 {early_avg:.4f}")
            beliefs.append("建议: 切换方向，不再微调当前参数空间")
        elif recent_avg > early_avg * 1.5:
            beliefs.append(f"加速提升: 最近3轮 Δ_avg={recent_avg:.4f} > 早期 {early_avg:.4f} → 当前方向值得深挖")
        elif len(passed) >= 5 and all(d > 0.001 for d in deltas[-5:]):
            beliefs.append(f"连续{len(passed)}轮提升 → 方向被验证有效")

    # 2. 失败模式
    if failed:
        fail_types = defaultdict(int)
        for r in failed:
            h = r.get("hypothesis", "")
            if "ENRICH" in h or "丰富" in h:
                fail_types["丰富映射表"] += 1
            elif "ADD_MAPPING" in h or "新条目" in h:
                fail_types["新增条目"] += 1
            elif "CODE" in h or "code" in h.lower():
                fail_types["代码示例"] += 1
            elif "INTERLEAVE" in h or "交错" in h:
                fail_types["交错实验"] += 1
            else:
                fail_types["其他"] += 1

        worst = max(fail_types, key=fail_types.get)
        if fail_types[worst] >= 2:
            beliefs.append(f"失败模式: '{worst}' 类操作连续{fail_types[worst]}次无效 → 避免这类改动")

    # 3. 因果链确认
    if len(passed) >= 2:
        effective_ops = set()
        for r in passed[-5:]:
            h = r.get("hypothesis", "")
            for op in ["EXPAND", "ENRICH", "DEEPEN", "ADD_MAPPING"]:
                if op in h:
                    effective_ops.add(op)
        if effective_ops:
            beliefs.append(f"有效操作: {', '.join(sorted(effective_ops))}")

    return "\n".join(f"- {b}" for b in beliefs) if beliefs else "- 尚无明确模式"


# ============================================================
# LLM: Predict-then-Attribute (需要 API)
# ============================================================

def _llm_attribute(
    round_num: int,
    hypothesis: str,
    predicted_delta: float,
    actual_delta: float,
    prev_beliefs: list[dict],
) -> str:
    """调用 LLM 做归因并重写信念。

    对应 Karpathy Arm 4:
      prediction → run → compare (delta_actual vs delta_predicted)
      → attribute (为什么准/不准) → rewrite beliefs
    """
    try:
        import openai
    except ImportError:
        return ""

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", None)

    if not api_key:
        return ""

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    # 构建 prompt
    prev_text = "\n".join(
        f"- R{e.get('round','?')}: {e.get('lesson','')}"
        for e in (prev_beliefs or [])[-10:]
    ) or "(无)"

    prompt = f"""你是实验归因分析器。分析以下 TaskLoop 实验并更新信念。

## 本轮
- 假设: {hypothesis}
- 预测 Δ: {predicted_delta:+.4f}
- 实际 Δ: {actual_delta:+.4f}
- 命中? {'是' if abs(actual_delta - predicted_delta) < 0.01 else '否 — ' + ('高估' if predicted_delta > actual_delta else '低估')}

## 之前的信念
{prev_text}

## 要求
基于实际结果重写信念列表（≤10条，每条一行 "- xxx"）。
- 如果预测不准，说明为什么
- 如果实际提升，提取通用教训
- 如果实际无效，说明可能的根因
- 删除已被证伪的旧信念
- 保留仍成立的旧信念

信念列表:"""

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("BELIEF_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception:
        return ""


# ============================================================
# 回调工厂
# ============================================================

def make_belief_callback():
    """创建 belief_callback，自动选择可用模式。

    返回的函数签名: (round_num, hypothesis, predicted_delta, actual_delta, beliefs_text) → new_beliefs_text
    """
    # 检测 LLM 可用性
    has_api = bool(os.environ.get("OPENAI_API_KEY", ""))

    # 持久化轮次数据（用于模式分析）
    rounds_history: list[dict] = []

    def callback(round_num, hypothesis, predicted_delta, actual_delta, beliefs_text):
        rounds_history.append({
            "round": round_num,
            "hypothesis": hypothesis,
            "predicted_delta": predicted_delta,
            "actual_delta": actual_delta,
            "passed": actual_delta > 0,
            "delta": actual_delta,
        })

        # 优先 LLM
        if has_api:
            # 解析现有信念为 dict 列表
            prev_entries = []
            for line in (beliefs_text or "").split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    prev_entries.append({"lesson": line[2:]})

            llm_result = _llm_attribute(
                round_num, hypothesis, predicted_delta,
                actual_delta, prev_entries,
            )
            if llm_result:
                return llm_result

        # 回退: 增强模式分析（每次重写，不追加）
        return _analyze_patterns(rounds_history)

    return callback
