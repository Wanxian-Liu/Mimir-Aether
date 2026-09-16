"""回归测试：`mimir_cli` 入口的两处同源缺陷（2026-09-16 修复）。

背景（均由「维护 GitHub 项目 / 让 CI 跑绿」取证时机械发现，非目测）：

**缺陷 ①（重复块）** `mimir_cli/main.py` 曾含 128 行重复块
（`L52..L179 ≡ L191..L319`，机械核实：滑窗哈希 + 逐行同构比对）⇒
`_apply_profile_override` 被**定义两次、调用两次**，`load_hermes_dotenv` /
`_setup_logging` / `apply_ipv4_preference` 等 **import 期副作用跑两遍**。

**缺陷 ②（`-p` 劫持）** `_apply_profile_override()` 不校验就认领 `argv` 里的任意
`-p <值>`。`-p` 是极常见的宿主工具旗标（pytest `-p no:randomly`）
⇒ 把 `"no:randomly"` 当 profile ⇒ `validate_profile_name` 抛 ValueError ⇒ `sys.exit(1)`
⇒ **任何 argv 含 `-p <非profile名>` 的进程，一 import 本模块就直接退出**。
实测后果：`pytest -p no:randomly` 让本仓 17 个 CLI 测试整片假红（与测试逻辑无关）。

本文件把两处都钉死：
- `TestIsValidProfileName`        新判据的语义边界；
- `TestForeignPFlagNotHijacked`   外来 `-p` 必须被放行（子进程真跑，非 mock）；
- `TestOwnProfileFlagStillClaimed` 自家 `-p <合法名>` 必须仍被认领（防修过头）；
- `TestEntrypointHasNoDuplicateBlock` 结构闸：副作用块必须**各只有一份**。
"""
import ast
import pathlib
import subprocess
import sys

import pytest

from mimir_cli.profiles import is_valid_profile_name

REPO = pathlib.Path(__file__).resolve().parent.parent
MAIN_PY = REPO / "mimir_cli" / "main.py"

# 在**子进程**里 import 入口模块并回显状态。必须子进程：缺陷发生在 import 期，
# 同进程内被测模块早已加载（且被 pytest 的 argv 污染），无法复现。
_PROBE = (
    "import sys, os;"
    "import mimir_cli.main;"
    "print('IMPORT_OK');"
    "print('ARGV=' + repr(sys.argv[1:]))"
)


def _run_entry(argv):
    return subprocess.run(
        [sys.executable, "-c", _PROBE] + argv,
        cwd=str(REPO), capture_output=True, text=True, timeout=180,
    )


# ── 1. 新判据的语义边界 ────────────────────────────────────────────────────

class TestIsValidProfileName:
    @pytest.mark.parametrize("name", ["default", "a", "abc123", "a-b_c", "x" * 64])
    def test_valid(self, name):
        assert is_valid_profile_name(name) is True

    @pytest.mark.parametrize("name", [
        "", "no:randomly", "NO:randomly", "no:cacheprovider",   # ← 真实踩坑值
        "-x", "a b", "x" * 65, "A", "_x",
    ])
    def test_invalid(self, name):
        assert is_valid_profile_name(name) is False

    @pytest.mark.parametrize("bad", [None, 123, [], object()])
    def test_non_string_never_raises(self, bad):
        """判据是「决定」不是「失败」：非字符串只能返回 False，不得抛。"""
        assert is_valid_profile_name(bad) is False


# ── 2. 外来 -p 必须被放行 ──────────────────────────────────────────────────

class TestForeignPFlagNotHijacked:
    @pytest.mark.parametrize("argv", [
        ["-p", "no:randomly"],          # pytest 真身（本次踩坑值）
        ["-p", "no:cacheprovider"],
        ["--profile=no:randomly"],
    ])
    def test_import_does_not_exit(self, argv):
        r = _run_entry(argv)
        assert r.returncode == 0, f"import 被外来旗标打断：rc={r.returncode}\n{r.stderr[-600:]}"
        assert "IMPORT_OK" in r.stdout

    def test_host_argv_is_left_intact(self):
        """不被认领 ⇒ 不得改写宿主 argv（否则宿主工具自己的解析会坏）。"""
        r = _run_entry(["-p", "no:randomly"])
        assert "ARGV=['-p', 'no:randomly']" in r.stdout.replace('"', "'")

    def test_this_repo_suite_survives_pytest_p_flag(self):
        """端到端：本仓测试在全量 pytest 带 `-p no:randomly` 时不再整片假红。

        只跑最小的 CLI 冒烟子集（快），真身由 CI 全量覆盖。
        """
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_mimir_cli_smoke.py",
             "-q", "-p", "no:randomly", "--no-header"],
            cwd=str(REPO), capture_output=True, text=True, timeout=300,
        )
        assert r.returncode == 0, f"带 -p 时 CLI 冒烟仍红：\n{r.stdout[-1500:]}"


# ── 3. 自家旗标必须仍被认领（防修过头）────────────────────────────────────

class TestOwnProfileFlagStillClaimed:
    def test_valid_but_missing_profile_is_still_claimed(self):
        """合法但不存在的 profile ⇒ 必须仍在**预解析**阶段认领并报清晰错误。

        若修过头（一律放行），`-p ghost` 会漏给 argparse，报错信息变成
        「unrecognized arguments」而非「Profile 'ghost' does not exist」。
        """
        r = _run_entry(["-p", "ghost-profile-does-not-exist"])
        assert r.returncode != 0
        assert "does not exist" in r.stderr, r.stderr[-600:]


# ── 4. 结构闸：重复块不得回潮 ──────────────────────────────────────────────

class TestEntrypointHasNoDuplicateBlock:
    """缺陷 ① 的护栏。重复块一旦被误贴回来，这里必须红。"""

    @pytest.mark.parametrize("marker", [
        "PROJECT_ROOT = Path",
        "def _apply_profile_override",
        "logger = logging.getLogger(__name__)",
        "load_hermes_dotenv(project_env",
    ])
    def test_setup_markers_appear_once(self, marker):
        n = MAIN_PY.read_text(encoding="utf-8").count(marker)
        assert n == 1, f"{marker!r} 出现 {n} 次（应为 1）⇒ 疑似重复块回潮"

    def test_apply_profile_override_called_exactly_once(self):
        """按**整行精确匹配**统计调用点（不能子串匹配：def 行里也含该子串）。"""
        n = sum(1 for l in MAIN_PY.read_text(encoding="utf-8").splitlines()
                if l.rstrip() == "_apply_profile_override()")
        assert n == 1, f"模块级调用点有 {n} 处（应为 1）⇒ import 期副作用会跑多遍"

    def test_ast_has_single_function_and_single_module_call(self):
        """AST 级复核（比字符串计数更难被绕过）。"""
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        defs = [n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_apply_profile_override"]
        calls = [n for n in tree.body
                 if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                 and isinstance(n.value.func, ast.Name)
                 and n.value.func.id == "_apply_profile_override"]
        assert len(defs) == 1, f"顶层定义 {len(defs)} 个（应为 1）"
        assert len(calls) == 1, f"顶层调用 {len(calls)} 个（应为 1）"
