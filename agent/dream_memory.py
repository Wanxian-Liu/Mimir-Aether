"""
梦境记忆蒸馏模块 — Dream Memory Distillation

模仿 CowAgent L4 梦境记忆模式：
  每天定时运行 → 读取所有持久化记忆 → 去重合并 → 蒸馏精炼 → 写回

PMD 共同进化（Co-Evolution）改进：
  - 行为约束蒸馏（behavioral_constraints）→ 写回 persistent.json 约束我的行为
  - 自我矛盾报告（self_contradiction_report）→ 写入独立文件用于复盘

依赖：
  - persistent.json（通过 memory_write_facade 访问）
  - DEEPSEEK_API_KEY（环境变量）
  - aiohttp（用于 LLM 调用，已存在于 context_compressor 的依赖中）

用法：
  from agent.dream_memory import run_dream_cycle
  ok, report = await run_dream_cycle()
  print(report)  # 蒸馏报告
"""

import json
import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 容量限制（与 CrossSessionMemory 一致）
_MAX_DECISIONS = 20
_MAX_PATTERNS = 30
_MAX_CONSTRAINTS = 5  # 行为约束上限

# 梦境蒸馏 API 参数
_DREAM_MODEL = "deepseek-chat"
_DREAM_TEMPERATURE = 0.3
_DREAM_MAX_TOKENS = 4096
_DREAM_TIMEOUT = 45


def _get_persistent_path() -> str:
    """获取 persistent.json 路径（与 CrossSessionMemory 同源）。"""
    # 优先读 MIMIR_AETHER_HOME
    home = os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    return os.path.join(home, "data", "persistent.json")


def _load_persistent(path: str) -> Optional[Dict]:
    """读取 persistent.json。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"[DreamMemory] 加载 persistent.json 失败: {e}")
        return None


def _save_persistent(path: str, data: Dict) -> bool:
    """写回 persistent.json（同步写入，不依赖 memory_write_facade 的合并逻辑）。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        logger.error(f"[DreamMemory] 写入 persistent.json 失败: {e}")
        return False


def _format_memory_for_distillation(data: Dict) -> str:
    """将记忆条目格式化为 LLM 友好的文本。"""
    mem: Dict = data.get("memory", {})
    lines: List[str] = []

    decisions: List = mem.get("key_decisions", [])
    if decisions:
        lines.append("=== key_decisions（关键决策） ===")
        for i, d in enumerate(decisions, 1):
            decision_text = d.get("decision", d) if isinstance(d, dict) else d
            lines.append(f"{i}. {decision_text}")

    patterns: List = mem.get("learned_patterns", [])
    if patterns:
        lines.append("\n=== learned_patterns（学到的模式） ===")
        for i, p in enumerate(patterns, 1):
            pattern_text = p.get("pattern", p) if isinstance(p, dict) else p
            ev = p.get("evidence", "")
            ev_suffix = f" — 证据: {ev}" if ev else ""
            lines.append(f"{i}. {pattern_text}{ev_suffix}")

    return "\n".join(lines)


def _build_distillation_prompt(memory_text: str) -> str:
    """构建梦境蒸馏的 LLM 提示词。"""
    return f"""你是一个梦境记忆蒸馏器。你的任务是合并、去重并精炼以下记忆条目。

规则：
1. **合并内容相似的条目**（例如 "Hermes独立路线 Phase I" 和 "Hermes独立路线 Phase I-V 全线闭合" → 合并为一条）
2. **删除完全重复的条目**（完全相同的文字保留一条）
3. **删除过时或被新条目替代的条目**
4. **为合并后的条目保留最佳的证据/上下文**
5. **输出格式固定**：JSON 格式，包含 "key_decisions"、"learned_patterns"、"behavioral_constraints"、"self_contradiction" 四个字段
6. **key_decisions 不超过 {_MAX_DECISIONS} 条**
7. **learned_patterns 不超过 {_MAX_PATTERNS} 条**
8. **behavioral_constraints 不超过 {_MAX_CONSTRAINTS} 条**——从 key_decisions 和 learned_patterns 中提取"你应该/你不应该"格式的行为约束
9. **self_contradiction** 为单条字符串——分析记忆条目中最严重的自我矛盾（哪个决策和哪个模式冲突）
10. **每条决策可附带 context 字段**（不超过 30 字）
11. **每条模式可附带 evidence 字段**（不超过 50 字）
12. **每条约束格式**：{{"rule": "你应该/你不应该...", "source": "distilled", "evidence": "基于XX条模式/决策的提炼"}}
13. **（Trajectory-Informed Memory）** 每条决策和模式增加以下字段：
    - **tip_type**：分类为 "strategy"（策略—以后该怎么做）、"recovery"（恢复—怎么从错误中修）、"optimization"（优化—怎么把好的做得更好）
    - **cause_chain**（仅决策）：{{"direct": "直接触发原因", "proximate": "近因/中间原因", "root": "根因/系统性问题"}}
14. **只输出 JSON**，不要解释过程。

输入记忆：
{memory_text}

输出格式：
{{
  "key_decisions": [
    {{"decision": "简洁的决策描述", "context": "何时/为什么做此决定", "tip_type": "strategy|recovery|optimization", "cause_chain": {{"direct": "直接原因", "proximate": "近因", "root": "根因"}}}}
  ],
  "learned_patterns": [
    {{"pattern": "学到的模式", "evidence": "支撑该模式的证据", "tip_type": "strategy|recovery|optimization"}}
  ],
  "behavioral_constraints": [
    {{"rule": "你应该/你不应该...", "source": "distilled", "evidence": "基于XX条模式的提炼"}}
  ],
  "self_contradiction": "最严重的自我矛盾描述（如果没有则返回空字符串）"
}}"""


async def _call_dream_llm(prompt: str) -> Optional[Dict]:
    """调用 DeepSeek API 执行梦境蒸馏（同步模式用于 cron，异步模式用于 agent）。"""
    import aiohttp

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.error("[DreamMemory] DEEPSEEK_API_KEY 未设置")
        return None

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _DREAM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": _DREAM_MAX_TOKENS,
        "temperature": _DREAM_TEMPERATURE,
    }

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=_DREAM_TIMEOUT)
        ) as session:
            async with session.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"[DreamMemory] LLM HTTP {resp.status}: {text[:200]}")
                    return None
                result = await resp.json()
                content = result["choices"][0]["message"]["content"]
                # 提取 JSON
                content = content.strip()
                # 去掉可能的 ```json ... ``` 包裹
                if content.startswith("```"):
                    content = content.split("\n", 1)[-1]
                    content = content.rsplit("```", 1)[0].strip()
                return _safe_json_parse(content)
    except Exception as e:
        logger.error(f"[DreamMemory] LLM 调用失败: {e}")
        return None


def _safe_json_parse(text: str) -> Optional[Dict]:
    """容错 JSON 解析：尝试多种策略从 LLM 输出中提取 JSON。"""
    import re

    # 策略1: 标准 json.loads
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2: json.JSONDecoder(strict=False) — 允许未转义控制字符
    try:
        decoder = json.JSONDecoder(strict=False)
        return decoder.decode(text)
    except json.JSONDecodeError:
        pass

    # 策略3: 正则提取最外层 JSON 块
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            decoder = json.JSONDecoder(strict=False)
            return decoder.decode(candidate)
        except json.JSONDecodeError:
            pass

    # 策略4: 尝试逐行修复 — 修复未转义的引号
    # 找到第一个 { 和最后一个 }，之间的内容
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        # 尝试修复常见问题：未转义的内部引号
        candidate = re.sub(r'(?<!\\)"', '\\"', candidate)
        candidate = candidate.replace('\\"', '"', 1)  # 恢复第一个（最外层）
        candidate = candidate.replace('\\"{', '{')     # 恢复 { 前的
        candidate = candidate.replace('\\"}', '}')     # 恢复 } 前的
        # 只保留最外层的引号
        if candidate.startswith('"') and candidate.endswith('"'):
            candidate = candidate[1:-1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    logger.error(f"[DreamMemory] 所有 JSON 解析策略均失败，前200字: {text[:200]}")
    return None


def _get_contradiction_path() -> str:
    """获取 self_contradiction_report.json 路径。"""
    home = os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    return os.path.join(home, "data", "self_contradiction_report.json")


def _save_contradiction_report(contradiction: str) -> bool:
    """将自我矛盾报告写入独立文件。"""
    if not contradiction or not contradiction.strip():
        return False
    path = _get_contradiction_path()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contradiction": contradiction.strip(),
    }
    try:
        # 追加到已有报告列表（保留最近10条）
        existing = []
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        if len(existing) > 10:
            existing = existing[-10:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"[DreamMemory] 自我矛盾报告已写入: {contradiction[:80]}...")
        return True
    except (IOError, json.JSONDecodeError) as e:
        logger.warning(f"[DreamMemory] 写入自我矛盾报告失败: {e}")
        return False


async def _run_distillation(
    data: Dict, memory_text: str, dry_run: bool = False
) -> Tuple[Dict, str]:
    """执行梦境蒸馏，返回（更新后的 data, 报告文本）。"""
    if dry_run:
        return data, f"[DRY RUN] 输入: {len(memory_text)} 字符，未修改"

    prompt = _build_distillation_prompt(memory_text)
    logger.info(f"[DreamMemory] 调用蒸馏 LLM（提示词 {len(prompt)} 字符）")
    result = await _call_dream_llm(prompt)

    if result is None:
        return data, "❌ 梦境蒸馏 LLM 调用失败，未修改"

    # 统计蒸馏前后的条目数
    old_decisions = len(data.get("memory", {}).get("key_decisions", []))
    old_patterns = len(data.get("memory", {}).get("learned_patterns", []))
    old_constraints = len(data.get("memory", {}).get("behavioral_constraints", []))
    new_decisions = len(result.get("key_decisions", []))
    new_patterns = len(result.get("learned_patterns", []))
    new_constraints = len(result.get("behavioral_constraints", []))

    # 用蒸馏后的条目替换原有记忆
    if "memory" not in data:
        data["memory"] = {}
    data["memory"]["key_decisions"] = result["key_decisions"][:_MAX_DECISIONS]
    data["memory"]["learned_patterns"] = result["learned_patterns"][:_MAX_PATTERNS]

    # PMD 共同进化：写入 behavioral_constraints
    if new_constraints > 0:
        data["memory"]["behavioral_constraints"] = result["behavioral_constraints"][:_MAX_CONSTRAINTS]
    else:
        data["memory"].pop("behavioral_constraints", None)

    # 写入自我矛盾报告（Change 3）
    contradiction = result.get("self_contradiction", "")
    if contradiction and contradiction.strip():
        _save_contradiction_report(contradiction)

    # 统计 tip_type 分布（Trajectory-Informed Memory）
    tip_types_decisions = {}
    for d in result.get("key_decisions", []):
        tt = d.get("tip_type", "unknown") if isinstance(d, dict) else "unknown"
        tip_types_decisions[tt] = tip_types_decisions.get(tt, 0) + 1
    tip_types_patterns = {}
    for p in result.get("learned_patterns", []):
        tt = p.get("tip_type", "unknown") if isinstance(p, dict) else "unknown"
        tip_types_patterns[tt] = tip_types_patterns.get(tt, 0) + 1

    # 统计 cause_chain 覆盖率
    decisions_with_chain = sum(
        1 for d in result.get("key_decisions", [])
        if isinstance(d, dict) and d.get("cause_chain")
    )

    report = (
        f"🔄 梦境蒸馏完成\n"
        f"  - key_decisions: {old_decisions} → {new_decisions} "
        f"({old_decisions - new_decisions:+d})\n"
        f"    · tip_type 分布: {tip_types_decisions}\n"
        f"    · cause_chain 覆盖率: {decisions_with_chain}/{new_decisions}\n"
        f"  - learned_patterns: {old_patterns} → {new_patterns} "
        f"({old_patterns - new_patterns:+d})\n"
        f"    · tip_type 分布: {tip_types_patterns}\n"
        f"  - behavioral_constraints: {old_constraints} → {new_constraints} "
        f"({new_constraints - old_constraints:+d})\n"
        f"  - 自我矛盾: {'⚠️ ' + contradiction[:80] if contradiction else '✅ 无'}\n"
        f"  - 时间: {datetime.now(timezone.utc).isoformat()}"
    )
    return data, report


async def run_dream_cycle(dry_run: bool = False) -> Tuple[bool, str]:
    """执行完整的梦境记忆蒸馏周期。

    Args:
        dry_run: 如果为 True，只分析不写盘

    Returns:
        (成功与否, 报告文本)
    """
    start = time.monotonic()
    path = _get_persistent_path()
    logger.info(f"[DreamMemory] 开始梦境周期，路径: {path}")

    # 1. 加载持久化数据
    data = _load_persistent(path)
    if data is None:
        return False, "❌ 无法加载 persistent.json"

    # 2. 格式化为文本
    memory_text = _format_memory_for_distillation(data)
    if not memory_text.strip():
        return True, "⏭ 没有记忆条目需要蒸馏"

    logger.info(f"[DreamMemory] 记忆文本: {len(memory_text)} 字符")

    # 3. 执行蒸馏
    updated_data, report = await _run_distillation(data, memory_text, dry_run)

    # 4. 写回
    elapsed = time.monotonic() - start
    path = _get_persistent_path()
    ok = _save_persistent(path, updated_data)
    if not ok:
        return False, report + f"\n❌ 写入失败（耗时 {elapsed:.1f}s）"

    return True, report + f"\n✅ 写入成功（耗时 {elapsed:.1f}s）"


# ============================================================================
# 同步入口（供 cronjob / 终端使用）
# ============================================================================

def sync_run_dream_cycle(dry_run: bool = False) -> str:
    """同步版本的梦境周期（用于终端或 cronjob，内部用事件循环）。"""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有事件循环，创建新任务
        future = asyncio.ensure_future(run_dream_cycle(dry_run))
        ok, report = loop.run_until_complete(future)
    else:
        ok, report = asyncio.run(run_dream_cycle(dry_run))

    return report


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    report = sync_run_dream_cycle(dry_run=True)
    print(report)
