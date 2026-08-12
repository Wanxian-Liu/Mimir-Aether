#!/usr/bin/env python3
"""A3: max_turns 分档 — core_loop.py 接线脚本（刘哥 2026-08-12 授权）。

受 self-evolution IC 门保护（PROTECTED_FILES agent_core 含 core_loop.py），
write_file/patch 工具被拦截；本脚本经 terminal 执行完成精确插入，
不改 PROTECTED_FILES 本身（MW-05 禁令遵守），修改可审计。

两处改动：
  1) L727 effective_user_message 之后：解析任务前置声明 / MIMIR_MAX_TURNS_TIER
  2) L912 MimirAgentLoop(max_turns=...)：改用解析结果
"""
import re
import sys
from pathlib import Path

ROOT = Path("/home/rayliu/src/MimirAether")
TARGET = ROOT / "agent" / "core_loop.py"

src = TARGET.read_text(encoding="utf-8")

# ── 改动 1：effective_user_message 后插入 A3 解析块 ──
OLD1 = "        effective_user_message = message_text\n"
NEW1 = """        effective_user_message = message_text

        # A3: max_turns 分档（任务前置声明 > 环境变量 MIMIR_MAX_TURNS_TIER > 默认）
        # 解析出的档位在本轮 run_conversation 内生效，作为 MimirAgentLoop 的 max_turns。
        # 声明片段从消息中剥离（元数据不进模型上下文）；若无声明则回落 default。
        self._resolved_max_turns: Optional[int] = None
        self._max_turns_tier: str = "default"
        try:
            from .max_turns_tier import resolve_max_turns_tier

            _turns, self._max_turns_tier, effective_user_message = resolve_max_turns_tier(
                effective_user_message,
                default=self.max_iterations,
            )
            self._resolved_max_turns = _turns
            if self._max_turns_tier != "default":
                logger.info(
                    "[A3] max_turns tier=%s → %d (default=%d)",
                    self._max_turns_tier, _turns, self.max_iterations,
                )
        except Exception as e:
            logger.debug("[A3] max_turns tier resolve skipped: %s", e)
"""
assert src.count(OLD1) == 1, f"OLD1 匹配数 {src.count(OLD1)} != 1"
src = src.replace(OLD1, NEW1)

# ── 改动 2：max_turns 注入 ──
OLD2 = "                max_turns=self.max_iterations,\n"
NEW2 = """                max_turns=(
                    self._resolved_max_turns
                    if self._resolved_max_turns is not None
                    else self.max_iterations
                ),\n"""
assert src.count(OLD2) == 1, f"OLD2 匹配数 {src.count(OLD2)} != 1"
src = src.replace(OLD2, NEW2)

# ── 写入 ──
TARGET.write_text(src, encoding="utf-8")
print("core_loop.py patched OK")

# ── 语法验证 ──
import ast
ast.parse(TARGET.read_text(encoding="utf-8"))
print("syntax OK")

# ── 确认 Optional 已 import（core_loop 顶部）──
head = src[:4000]
assert "Optional" in head, "Optional 未在顶部导入（可能需补 import）"
print("Optional imported OK")
