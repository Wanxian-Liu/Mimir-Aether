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
    @pytest.mark.parametrize("name", ["a", "abc123", "a-b_c", "x" * 64])
    def test_valid(self, name):
        assert is_valid_profile_name(name) is True

    @pytest.mark.parametrize("name", [
        "", "no:randomly", "NO:randomly", "no:cacheprovider",   # ← 真实踩坑值
        "-x", "a b", "x" * 65, "A", "_x",
        "default",   # ← C-2/H5：解析层别名 != 可认领的旗标值（宿主工具 -p default）
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



# ── 5. C-2 / H5：宿主工具名单白名单（2026-09-17 · Loki Action a）────────────

class TestHostToolWhitelistJudgement:
    """纯判据层：名单命中判定（不起子进程）。"""

    @pytest.mark.parametrize("prog", [
        "pytest", "/home/<user>/src/MimirAether/.venv/bin/pytest", "pytest.exe",
        "/venv/lib/python3.12/site-packages/pytest/__main__.py", "ruff", "uv",
    ])
    def test_known_host_tool_programs(self, prog):
        from mimir_cli.profiles import is_host_tool_program
        assert is_host_tool_program(prog) is True

    @pytest.mark.parametrize("prog", [
        "mimir", "/usr/local/bin/mimir", "", None, "python3", "-c", "__main__.py",
    ])
    def test_unknown_programs_are_not_host_tools(self, prog):
        from mimir_cli.profiles import is_host_tool_program
        assert is_host_tool_program(prog) is False

    @pytest.mark.parametrize("val", ["no:randomly", "no:cacheprovider", "xdist", "NO:RANDOMLY"])
    def test_known_host_tool_p_values(self, val):
        from mimir_cli.profiles import is_host_tool_p_value
        assert is_host_tool_p_value(val) is True

    @pytest.mark.parametrize("val", ["ghost", "mimir", "default", ""])
    def test_other_values_are_not_whitelisted(self, val):
        from mimir_cli.profiles import is_host_tool_p_value
        assert is_host_tool_p_value(val) is False

    def test_default_not_claimable_but_alias_survives(self):
        """DoD：`default` 不可被认领；但**解析层别名必须保住**（防修过头）。"""
        from mimir_cli.profiles import (get_profile_dir, is_valid_profile_name,
                                        validate_profile_name)
        assert is_valid_profile_name("default") is False     # 不可认领
        assert validate_profile_name("default") is None      # 别名：不抛
        assert get_profile_dir("default") is not None        # 别名：可解析


_TWIN = (
    "import sys, os;"
    "sys.argv = [{prog!r}, '-p', {name!r}];"
    "import mimir_cli.main;"
    "print('IMPORT_OK');"
    "print('ARGV=' + repr(sys.argv[1:]));"
    "print('HH=' + str(bool(os.environ.get('HERMES_HOME'))))"
)


def _twin(prog, name):
    return subprocess.run([sys.executable, "-c", _TWIN.format(prog=prog, name=name)],
                          cwd=str(REPO), capture_output=True, text=True, timeout=180)


class TestHostToolWhitelistTwinArms:
    """**双胞臂**：同一个 `-p <合法 profile 名>`，只改「进程身份」这一个变量。

    正臂（宿主工具）必须**不认领**；负臂（自家 mimir）必须**认领**。
    两臂读数相反 ⇒ 白名单有鉴别力（不是「一律放行」）。
    """

    def test_arm_host_tool_does_not_claim(self):
        """正臂：宿主工具进程 ⇒ **不认领**（rc=0 / import 成 / argv 一字未改）。"""
        r = _twin("pytest", "ghost-profile-does-not-exist")
        assert r.returncode == 0, "宿主工具进程里被认领了 rc=%d stderr=%s" % (
            r.returncode, r.stderr[-400:])
        assert "IMPORT_OK" in r.stdout
        assert "ARGV=['-p', 'ghost-profile-does-not-exist']" in r.stdout.replace('"', "'")
        assert "does not exist" not in r.stderr

    def test_arm_same_value_in_non_host_tool_is_claimed(self):
        """对照臂（**负控·单变量**）：同一 `-p` 值，只把 argv0 换成非宿主工具 ⇒ 必须认领。

        `ghost-profile-does-not-exist` 本身是**合法形状**的 profile 名 ⇒ 若前一臂是
        「值不像 profile」起的作用，本臂也应 rc=0；实测 rg=1（认领）⇒ 判别变量是
        **进程身份**，即名单白名单本体。

        ⚠️ 本 run 自曝：初版断言 `HERMES_HOME` 为空 —— 那是**探针形状错误**：
        该变量在 main.py 后续 `load_hermes_dotenv` 里同样会被设（实测 `HH=True`），
        与「是否认领」无关 ⇒ 已剔除，改用 argv/rc 两个**认领独有的**可观测改写量。
        """
        r = _twin("-c", "ghost-profile-does-not-exist")
        assert r.returncode != 0, "非宿主工具进程里未认领（修过头）stdout=%s" % r.stdout[-300:]
        assert "does not exist" in r.stderr

    def test_arm_own_cli_still_claims(self):
        r = _twin("mimir", "ghost-profile-does-not-exist")
        assert r.returncode != 0, "自家 CLI 未认领（修过头）stdout=%s" % r.stdout[-300:]
        assert "does not exist" in r.stderr

    def test_arm_default_value_never_claimed_by_our_cli(self):
        """DoD 另一半：自家 CLI 的 `-p default` 也不认领（默认值由回落逻辑管）。"""
        r = _twin("mimir", "default")
        assert r.returncode == 0, "rc=%d stderr=%s" % (r.returncode, r.stderr[-400:])
        assert "IMPORT_OK" in r.stdout
        assert "ARGV=['-p', 'default']" in r.stdout.replace('"', "'"), "argv 被改写了"

    def test_arm_long_flag_unaffected_by_host_tool_whitelist(self):
        """长旗标无歧义 ⇒ 即使在宿主工具进程里也应认领（否则白名单修过头）。"""
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys;sys.argv=['pytest','--profile=ghost-profile-does-not-exist'];"
             "import mimir_cli.main;print('IMPORT_OK')"],
            cwd=str(REPO), capture_output=True, text=True, timeout=180)
        assert r.returncode != 0, "长旗标被白名单误伤：stdout=%s" % r.stdout[-300:]
        assert "does not exist" in r.stderr
