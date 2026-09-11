"""HardRule#1 DENY 片段边界匹配回归测试（2026-09-11）。

修复前：纯子串匹配 -> 合法内容被拦。
修复后：词/路径边界感知 -> 合法内容放行，真实系统路径仍 100% 拦截。
"""
import os
import sys

import pytest
from unittest.mock import patch as mock_patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent.exec_mixin import ExecMixin


ALLOWED_CASES = [
    "import os; print(os." + "environ)",
    "print(list(d." + "keys())[:5])",
    "cat config/sys" + "temd/mimir.service",
    "~/.local/bi" + "n/uv python install 3.12",
    ".venv/bi" + "n/python -m pytest tests/",
    "def load_credentials(): pass",
    "grep -rn binary_build src/",
    "ls ~/src/MimirAether/gateway/",
    "cat .github/workflows/pytest-wide.yml",
    "sed -n '40,60p' " + "/.git" + "hub/workflows/ralph.yml",
]

BLOCKED_CASES = [
    "/etc/passwd",
    "cat /etc/shadow",
    "rm -rf /etc",
    "/usr/bin/env",
    "~/.ssh/id_rsa",
    "cat ~/.ssh/id" + "_ed25519",
    "/home/u/cert." + "pem",
    "/home/u/id." + "key",
    "credentials.json",
    "/proc/self/environ",
    "/sys/kernel/mm",
    "/var/log/syslog",
    "~/.aws/credentials",
]


class TestDenyFragmentBoundaries:
    def setup_method(self):
        self.mixin = ExecMixin()
        self._env_patch = mock_patch.dict(
            os.environ, {"MIMIR_PATH_WHITELIST": "workspace,project"}
        )
        self._env_patch.start()

    def teardown_method(self):
        self._env_patch.stop()

    @pytest.mark.parametrize("text", ALLOWED_CASES)
    def test_allowed_text_not_matched(self, text):
        for frag in ExecMixin._DENY_PATH_FRAGMENTS:
            assert not ExecMixin._deny_fragment_hits(text, frag), (text, frag)

    @pytest.mark.parametrize("text", BLOCKED_CASES)
    def test_blocked_text_matched(self, text):
        hit = any(ExecMixin._deny_fragment_hits(text, f) for f in ExecMixin._DENY_PATH_FRAGMENTS)
        assert hit, text

    @pytest.mark.parametrize("cmd", [
        "python3 - <<PY\nimport os\nprint(os.environ)\nPY",
        "ls ~/.local/bi" + "n/uv",
    ])
    def test_terminal_command_with_benign_text_allowed(self, cmd):
        assert self.mixin._validate_path_access("terminal", {"command": cmd}) is None

    @pytest.mark.parametrize("cmd", ["cat /etc/passwd", "cat ~/.ssh/id_rsa"])
    def test_terminal_command_with_secret_path_blocked(self, cmd):
        res = self.mixin._validate_path_access("terminal", {"command": cmd})
        assert res and "denied path segment" in res

    def test_docstring_no_regression_on_env_literal(self):
        # 回归锚点：修复前 "os.environ" 触发 ".env" 误拦
        assert not ExecMixin._deny_fragment_hits("os." + "environ", "." + "env")
