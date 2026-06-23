"""
梦境记忆蒸馏模块 — Dream Memory Distillation

模仿 CowAgent L4 梦境记忆模式：
  每天定时运行 → 读取所有持久化记忆 → 去重合并 → 蒸馏精炼 → 写回

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

# 梦境蒸馏 API 参数
_DREAM_MODEL = "deepseek-chat"
_DREAM_TEMPERATURE = 0.3
_DREAM_MAX_TOKENS = 2048
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
5. **输出格式固定**：JSON 格式，包含 "key_decisions" 和 "learned_patterns" 两个数组
6. **key_decisions 不超过 {_MAX_DECISIONS} 条**
7. **learned_patterns 不超过 {_MAX_PATTERNS} 条**
8. **每条决策可附带 context 字段**（不超过 30 字）
9. **每条模式可附带 evidence 字段**（不超过 50 字）
10. **只输出 JSON**，不要解释过程。

输入记忆：
{memory_text}

输出格式：
{{
  "key_decisions": [
    {{"decision": "简洁的决策描述", "context": "何时/为什么做此决定"}}
  ],
  "learned_patterns": [
    {{"pattern": "学到的模式", "evidence": "支撑该模式的证据"}}
  ]
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
                return json.loads(content)
    except Exception as e:
        logger.error(f"[DreamMemory] LLM 调用失败: {e}")
        return None


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
    new_decisions = len(result.get("key_decisions", []))
    new_patterns = len(result.get("learned_patterns", []))

    # 用蒸馏后的条目替换原有记忆
    if "memory" not in data:
        data["memory"] = {}
    data["memory"]["key_decisions"] = result["key_decisions"][:_MAX_DECISIONS]
    data["memory"]["learned_patterns"] = result["learned_patterns"][:_MAX_PATTERNS]

    report = (
        f"🔄 梦境蒸馏完成\n"
        f"  - key_decisions: {old_decisions} → {new_decisions} "
        f"({old_decisions - new_decisions:+d})\n"
        f"  - learned_patterns: {old_patterns} → {new_patterns} "
        f"({old_patterns - new_patterns:+d})\n"
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
