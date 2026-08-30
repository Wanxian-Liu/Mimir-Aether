"""架构硬规则 #1 阶段 1：路径白名单测试（2026-08-18 Hermes · OpenClaw security 方案）

验证：文件操作工具路径分级——workspace 允许读写 / project 只读 / 系统与密钥目录禁止；
env 门控 MIMIR_PATH_WHITELIST=off 回全权限。
"""
import os
import sys
import pytest

# 固定真实 HOME（2026-08-18 偏差根因修复：Mimir execute_code 沙箱 HOME 被覆盖为
# ~/.mimiraether，导致 expanduser("~") 解析错位——project 用例硬编码真实路径被判
# "outside allowed paths"（32+2 假失败，与 Hermes 收束声明 34 passed 冲突）。
# 从 passwd 数据库取真实 home，不受沙箱 HOME env 覆盖影响。）
try:
    import pwd
    os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
except (ImportError, KeyError):
    pass  # 非 POSIX 平台保持原样

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.exec_mixin import ExecMixin


class _FakeExec(ExecMixin):
    def __init__(self):
        self._tool_errors = []


@pytest.fixture()
def exec_obj():
    return _FakeExec()


# ── 非文件工具放行 ──
def test_non_path_tool_ok(exec_obj):
    assert exec_obj._validate_path_access("web_search", {"query": "x"}) is None


# ── 系统目录拒绝 ──
def test_etc_passwd_denied(exec_obj):
    err = exec_obj._validate_path_access("read_file", {"path": "/etc/passwd"})
    assert err and "Blocked by path whitelist" in err


# ── 密钥目录拒绝 ──
def test_ssh_key_denied(exec_obj):
    err = exec_obj._validate_path_access("read_file", {"path": os.path.expanduser("~/.ssh/id_rsa")})
    assert err and "Blocked" in err


def test_aws_credentials_denied(exec_obj):
    err = exec_obj._validate_path_access("read_file", {"path": os.path.expanduser("~/.aws/credentials")})
    assert err and "Blocked" in err


# ── workspace 允许读写 ──
def test_workspace_write_ok(exec_obj):
    p = os.path.expanduser("~/.mimiraether/tmp/test.md")
    assert exec_obj._validate_path_access("write_file", {"path": p}) is None


def test_wiki_read_ok(exec_obj):
    p = os.path.expanduser("~/wiki/discussions/x.md")
    assert exec_obj._validate_path_access("read_file", {"path": p}) is None


# ── project 只读 ──
def test_project_write_denied(exec_obj):
    p = os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/agent/agent_loop.py"
    err = exec_obj._validate_path_access("write_file", {"path": p})
    assert err and "read-only" in err


def test_project_read_ok(exec_obj):
    p = os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/agent/agent_loop.py"
    assert exec_obj._validate_path_access("read_file", {"path": p}) is None


# ── env 门控 off 回全权限 ──
def test_gate_off_deny_still_active(exec_obj, monkeypatch):
    """E2 审计修复：off 仅解除白名单分级——DENY 路径永远拒绝"""
    monkeypatch.setenv("MIMIR_PATH_WHITELIST", "off")
    err = exec_obj._validate_path_access("read_file", {"path": "/etc/passwd"})
    assert err and "Blocked" in err  # DENY 永远生效（E2）
