#!/usr/bin/env python3
"""
SelfEvolutionEngine 生产接线脚本

用法:  python3 scripts/run_evolution.py [--candidate-dir agent/] [--dry-run]

效果:
  1. 扫描 candidate-dir 下 Python 文件
  2. 实例化 SelfEvolutionEngine
  3. 调用 run_cycle(execute_callback=write_safe_change)
  4. execute_callback 对推荐文件做安全微改（补漏缺类型标注/docstring）
  5. 验证 tier0 -> 回滚失败 -> 写 leder
  6. leder 出现第一条 outcome="success" 记录
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# ── 加到 sys.path 以导入 agent 模块 ──
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO))

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("run_evolution")


# ══════════════════════════════════════════════════════════════
#  辅助：安全微改
# ══════════════════════════════════════════════════════════════

def _add_simple_docstring(file_path: str) -> Optional[str]:
    """
    尝试给文件中的第一个无 docstring 的类或函数补一个最小 docstring。
    返回修改后的文件内容，若无可改则返回 None。
    """
    import ast

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    try:
        tree = ast.parse(original, filename=file_path)
    except SyntaxError:
        return None  # 语法错误跳过

    # 找第一个无 docstring 的 class/function def
    target_lineno = None
    target_name = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            # 如果有 docstring，它的 body[0] 是一个 Expr(value=Constant(...))
            has_doc = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            if not has_doc:
                target_lineno = node.lineno
                target_name = node.name
                break

    if target_lineno is None or target_name is None:
        return None  # 全部都已有 docstring

    # 在 def 或 class 行后插入 docstring
    lines = original.splitlines()
    kind = "class" if any(
        isinstance(n, ast.ClassDef) and n.lineno == target_lineno
        for n in ast.walk(tree)
    ) else "function"

    # 找插入位置：当前行后的第一个非空/非装饰器行
    insert_idx = target_lineno  # 0-indexed
    while insert_idx < len(lines) and (
        not lines[insert_idx].strip()
        or lines[insert_idx].strip().startswith("@")
    ):
        insert_idx += 1

    if insert_idx >= len(lines):
        return None

    indent = " " * (len(lines[insert_idx]) - len(lines[insert_idx].lstrip()))
    doc_line = f'{indent}"""{kind} auto-docstring. """'

    lines.insert(insert_idx, doc_line)
    return "\n".join(lines) + "\n"


def write_safe_change(file_path: str) -> dict:
    """
    对 file_path 施安全微改。
    返回 dict: {"outcome": "success" | "skipped" | "rolled_back", "tier0": ...}
    "rolled_back" 表示改动已写入但验证失败后回滚（语法错/tier0 失败/异常）。
    """
    logger.info("尝试安全微改: %s", file_path)

    if not os.path.isfile(file_path):
        return {"outcome": "skipped", "tier0": "not_run", "reason": "file_not_found"}

    modified = _add_simple_docstring(file_path)
    if modified is None:
        return {"outcome": "skipped", "tier0": "not_run", "reason": "no_improvement"}

    # 备份原文件
    backup = file_path + ".bak"
    with open(file_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    with open(backup, "w", encoding="utf-8") as f:
        f.write(original_content)

    try:
        # 写入修改
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified)

        # 验证：语法检查
        import ast
        with open(file_path, "r", encoding="utf-8") as f:
            new_content = f.read()
        try:
            ast.parse(new_content, filename=file_path)
        except SyntaxError as e:
            # 语法出错，回滚
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            os.remove(backup)
            return {"outcome": "rolled_back", "tier0": "not_run", "reason": f"syntax_error: {e}"}

        # 验证：tier0
        tier0_result = _run_tier0()
        if tier0_result["pass"]:
            os.remove(backup)  # 成功则删备份
            return {"outcome": "success", "tier0": tier0_result["summary"]}
        else:
            # 回滚
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            os.remove(backup)
            return {"outcome": "rolled_back", "tier0": tier0_result["summary"], "reason": "tier0_failed"}

    except Exception as e:
        # 异常时回滚
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_content)
        if os.path.exists(backup):
            os.remove(backup)
        return {"outcome": "rolled_back", "tier0": "not_run", "reason": str(e)}


def _run_tier0() -> dict:
    """运行 tier0，返回 {"pass": bool, "summary": str}"""
    logger.info("运行 tier0...")
    try:
        result = subprocess.run(
            ["./run_ralph_tier0.sh"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        summary = result.stdout.strip()[-200:] if result.stdout else ""
        passed = result.returncode == 0
        return {"pass": passed, "summary": summary}
    except subprocess.TimeoutExpired:
        return {"pass": False, "summary": "timeout (120s)"}
    except Exception as e:
        return {"pass": False, "summary": str(e)}


# ══════════════════════════════════════════════════════════════
#  主逻辑
# ══════════════════════════════════════════════════════════════

def main(candidate_dir: str, dry_run: bool = False):
    t0 = time.time()

    # 1. 收集候选文件
    base = Path(_REPO) / candidate_dir
    exclude_dirs = {"__pycache__", ".git", "self_evolution", "tests", "mimicore"}
    candidate_files: List[str] = []
    for pyfile in sorted(base.rglob("*.py")):
        if not any(excl in pyfile.parts for excl in exclude_dirs):
            candidate_files.append(str(pyfile))

    if not candidate_files:
        print("❌ 未找到候选 Python 文件")
        sys.exit(1)

    print(f"📦 候选文件: {len(candidate_files)} 个")
    for f in candidate_files[:5]:
        print(f"   {f}")
    if len(candidate_files) > 5:
        print(f"   ... 还有 {len(candidate_files) - 5} 个")

    # 2. 导入引擎
    from agent.self_evolution import SelfEvolutionEngine
    engine = SelfEvolutionEngine()

    # 3. 分析
    print(f"\n🔍 分析阶段...")
    analysis = engine.analyze(candidate_files)
    safe = analysis["plan"]["safe_files"]
    violations = analysis["plan"]["ic_violations"]
    print(f"   安全文件: {len(safe)}")
    print(f"   IC 违规:  {len(violations)}")
    for v in violations[:3]:
        print(f"     ⚠ {v}")

    if dry_run:
        print("\n⏸  --dry-run 模式，不执行进化")
        print(json.dumps(analysis, indent=2, ensure_ascii=False, default=str)[:500])
        return

    # 4. 执行进化
    print(f"\n🚀 执行进化...")
    report = engine.run_cycle(
        candidate_files=candidate_files,
        execute_callback=write_safe_change,
        run_tier0=True,
    )

    # 5. 输出结果
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"📊 进化报告")
    print(f"{'='*60}")
    print(f"   状态:      {report.status}")
    print(f"   耗时:      {elapsed:.1f}s")
    print(f"   结果:      {report.summary}")
    if report.record:
        print(f"   outcome:   {report.record.outcome}")
        print(f"   tier0:     {report.record.tier0_result}")
    print(f"\n账本路径: {SelfEvolutionEngine._ledger_path()}")
    print(f"{'='*60}\n")

    # 6. 读 leder
    try:
        with open(SelfEvolutionEngine._ledger_path(), "r", encoding="utf-8") as f:
            leder = json.load(f)
        print(f"📒 账本历史共 {len(leder)} 条:")
        for e in leder[-3:]:
            s = e.get("status", "?")
            ok = e.get("ok", "?")
            r = e.get("reason", "")
            print(f"   [{s}] ok={ok} | {r}")
    except Exception:
        pass

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SelfEvolutionEngine 生产接线")
    parser.add_argument("--candidate-dir", default="agent/",
                        help="扫描目录(相对于仓库根)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只分析不执行")
    args = parser.parse_args()
    main(args.candidate_dir, dry_run=args.dry_run)
