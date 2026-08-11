#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2 Recognition Memory — 检索结果 LLM 相关性过滤
================================================

方案: 7d73fa5 (Recognition Memory, 第三次实现)

定位: session_search_tool / 检索器返回候选结果后, 用 LLM 对
      (query, candidate) 逐条做语义相关性再认(recognition),
      过滤低相关项、保留高相关项并附理由, 降低检索噪声。

与朴素阈值(纯相似度分数)的区别: LLM 能理解语义等价、反问句式、
否定表达等相似度分数无法捕捉的信号, 且每条输出可解释理由。

设计原则:
  - fail-open: LLM 调用失败 → 原样返回全部候选(不丢召回)
  - 批量: 默认每批 20 条候选, 减少 API 调用次数
  - 严格 JSON: LLM 输出必须是 JSON, 解析失败按 fail-open 处理
  - 幂等: 输入输出均为 JSON, 便于管道对接与回归对比

输入格式 (stdin 或 --input 文件):
  {
    "query": "用户的检索问题",
    "candidates": [
      {"id": "...", "text": "候选内容", "score": 0.8, "meta": {...}},
      ...
    ]
  }

输出格式 (stdout 或 --output 文件):
  {
    "query": "...",
    "stats": {"total": N, "kept": K, "dropped": D, "llm_used": bool,
              "fallback_reason": null|str, "latency_s": 0.0},
    "kept":   [ {..., "recognition": {"relevant": true, "confidence": 0.9,
                                       "reason": "..."}} ],
    "dropped": [ {..., "recognition": {"relevant": false, "confidence": 0.1,
                                        "reason": "..."}} ]
  }

CLI:
  python3 p2_recognition_filter.py --input results.json --output filtered.json
  echo '{"query":"...","candidates":[...]}' | python3 p2_recognition_filter.py
  python3 p2_recognition_filter.py --input results.json --threshold 0.5 \
      --max-candidates 50 --batch-size 20 --dry-run

环境变量:
  DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL  (默认 deepseek-chat)
  P2_RECOGNITION_THRESHOLD (默认 0.5)

依赖: 仅标准库 (urllib/json), 无第三方依赖。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 常量与配置
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_THRESHOLD = 0.5
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_CANDIDATES = 100
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 2

SYSTEM_PROMPT = """你是 Recognition Memory 过滤器。给定一个检索问题(query)和若干候选结果,
判断每条候选是否与该问题语义相关。判定标准:
- 相关(relevant=true): 候选内容能实质回答/支撑/扩展该问题, 或与该问题讨论同一主题。
- 不相关(relevant=false): 候选与该问题主题无关, 或只是泛泛提及、无法实质支撑。

严格输出 JSON 数组, 不要输出任何其他文字。格式:
[{"index": 0, "relevant": true, "confidence": 0.9, "reason": "简短中文理由"},
 {"index": 1, "relevant": false, "confidence": 0.1, "reason": "简短中文理由"}]
其中 index 必须与输入序号一一对应, confidence 为 0~1 浮点数。"""


def _extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    """从 LLM 输出中稳健提取 JSON 数组(容忍 ```json 围栏与前后杂文)。"""
    if not text:
        return None
    # 去掉 markdown 代码围栏
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    # 定位第一个 '[' 与最后一个 ']'
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        # 容忍单引号等常见 LLM 幻觉
        try:
            data = json.loads(
                cleaned[start : end + 1].replace("'", '"')
            )
        except json.JSONDecodeError:
            return None
    if not isinstance(data, list):
        return None
    return [d for d in data if isinstance(d, dict)]


def _truncate(text: str, limit: int = 600) -> str:
    """截断候选文本, 避免超长内容撑爆 prompt。"""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[截断, 原长{len(text)}]"


def _candidate_text(cand: Dict[str, Any]) -> str:
    """从候选 dict 中取可判定的文本字段。"""
    for key in ("text", "content", "snippet", "summary", "message"):
        val = cand.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # 兜底: 序列化整个候选
    return json.dumps(cand, ensure_ascii=False)[:600]


# ---------------------------------------------------------------------------
# LLM 客户端 (OpenAI 兼容 /chat/completions, 仅标准库)
# ---------------------------------------------------------------------------

class RecognitionLLM:
    """极简 OpenAI 兼容客户端: POST /chat/completions, 返回首条 content。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> Optional[str]:
        """调用 chat completions, 返回 assistant content; 失败返回 None。"""
        if not self.api_key:
            return None
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 4000,
        }
        body = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return content
            except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
                if attempt >= self.max_retries:
                    return None
                time.sleep(1.5 * (attempt + 1))
        return None


# ---------------------------------------------------------------------------
# 核心过滤逻辑
# ---------------------------------------------------------------------------

def _build_batch_prompt(query: str, batch: List[Dict[str, Any]]) -> str:
    lines = [f"检索问题: {query}", "", "候选结果:"]
    for i, cand in enumerate(batch):
        lines.append(f"[{i}] {_truncate(_candidate_text(cand))}")
    lines.append("")
    lines.append('请输出 JSON 数组: [{"index": 序号, "relevant": true/false, "confidence": 0~1, "reason": "..."}]')
    return "\n".join(lines)


def filter_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    threshold: float = DEFAULT_THRESHOLD,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    llm: Optional[RecognitionLLM] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    核心入口: 对候选列表做 LLM 相关性再认过滤。

    返回 dict: {query, stats, kept, dropped}
      - stats.total / kept / dropped / llm_used / fallback_reason / latency_s
      - kept: 相关且 confidence >= threshold, 按 confidence 降序
      - dropped: 其余候选(含判定为不相关的)
    失败(LLM 不可用/输出不可解析) → fail-open: 全部进 kept, llm_used=False。
    """
    if not candidates:
        return {
            "query": query,
            "stats": {"total": 0, "kept": 0, "dropped": 0,
                      "llm_used": False, "fallback_reason": "no candidates",
                      "latency_s": 0.0},
            "kept": [], "dropped": [],
        }

    candidates = candidates[:max_candidates]
    total = len(candidates)
    started = time.monotonic()

    # 预置 recognition 字段结构
    def _decorate(cand: Dict[str, Any], verdict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        item = dict(cand)
        item["recognition"] = verdict or {
            "relevant": True,
            "confidence": 0.0,
            "reason": "未判定(LLM 不可用或解析失败)",
        }
        return item

    if dry_run:
        # 干跑: 不调用 LLM, 原样返回, 用于验证管道与对比基线
        kept = [_decorate(c, None) for c in candidates]
        return {
            "query": query,
            "stats": {"total": total, "kept": total, "dropped": 0,
                      "llm_used": False, "fallback_reason": "dry_run",
                      "latency_s": round(time.monotonic() - started, 3)},
            "kept": kept, "dropped": [],
        }

    llm = llm or RecognitionLLM()
    verdicts: List[Dict[str, Any]] = []
    llm_ok = True
    fallback_reason: Optional[str] = None

    for start in range(0, total, batch_size):
        batch = candidates[start : start + batch_size]
        prompt = _build_batch_prompt(query, batch)
        raw = llm.chat(prompt)
        parsed = _extract_json_array(raw) if raw else None
        if parsed is None:
            llm_ok = False
            fallback_reason = f"batch@{start}: LLM 输出不可解析" + ("" if raw else " (无输出/无key)")
            break
        # 按 index 对齐(容忍乱序与缺项)
        by_index = {int(v.get("index", -1)): v for v in parsed if isinstance(v.get("index"), (int, float))}
        for i in range(len(batch)):
            verdicts.append(by_index.get(i, {"index": i, "relevant": True,
                                             "confidence": 0.0, "reason": "LLM 未返回该条目"}))
    else:
        # for 正常结束 → 所有批次都解析成功
        pass

    if not llm_ok:
        # fail-open: 全部保留, 标注未过滤
        kept = [_decorate(c, None) for c in candidates]
        return {
            "query": query,
            "stats": {"total": total, "kept": total, "dropped": 0,
                      "llm_used": False, "fallback_reason": fallback_reason,
                      "latency_s": round(time.monotonic() - started, 3)},
            "kept": kept, "dropped": [],
        }

    kept, dropped = [], []
    for cand, verdict in zip(candidates, verdicts):
        relevant = bool(verdict.get("relevant", True))
        confidence = float(verdict.get("confidence", 0.0) or 0.0)
        reason = str(verdict.get("reason", ""))
        item = _decorate(cand, {"relevant": relevant, "confidence": confidence, "reason": reason})
        if relevant and confidence >= threshold:
            kept.append(item)
        else:
            dropped.append(item)

    kept.sort(key=lambda x: x["recognition"]["confidence"], reverse=True)
    return {
        "query": query,
        "stats": {"total": total, "kept": len(kept), "dropped": len(dropped),
                  "llm_used": True, "fallback_reason": None,
                  "latency_s": round(time.monotonic() - started, 3)},
        "kept": kept, "dropped": dropped,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P2 Recognition Memory — 检索结果 LLM 相关性过滤 (方案 7d73fa5)"
    )
    p.add_argument("--input", "-i", help="输入 JSON 文件(默认 stdin)")
    p.add_argument("--output", "-o", help="输出 JSON 文件(默认 stdout)")
    p.add_argument("--threshold", type=float, default=None,
                   help=f"相关性置信度阈值(默认 {DEFAULT_THRESHOLD} 或环境变量 P2_RECOGNITION_THRESHOLD)")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    p.add_argument("--dry-run", action="store_true", help="不调用 LLM, 只验证管道")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    threshold = args.threshold if args.threshold is not None else float(
        os.environ.get("P2_RECOGNITION_THRESHOLD", DEFAULT_THRESHOLD)
    )

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    query = data.get("query", "")
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        print(json.dumps({"error": "candidates must be a list"}, ensure_ascii=False), file=sys.stderr)
        return 2

    result = filter_candidates(
        query=query,
        candidates=candidates,
        threshold=threshold,
        batch_size=args.batch_size,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
    )

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
