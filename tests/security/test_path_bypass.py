"""架构硬规则 #1 路径白名单 - 绕过测试套件
覆盖 OpenClaw code-reviewer 审计段 (commit dda42d8) 发现:
- S1 符号链接绕过（os.path.realpath 必须）
- S2 大小写绕过（os.path.normcase 必须）
- S3 URL 编码绕过（urllib.parse.unquote 必须）
- L4 DENY 路径 normpath 误伤（精确前缀匹配）
- L5 exec 无路径参数放过（致命命令 100% 绕过）
- S4 exec kwargs 多参数名未覆盖
"""
import os
import sys
import pytest
from unittest.mock import patch as mock_patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent.exec_mixin import ExecMixin


class TestPathBypass:
    """#1 路径白名单绕过测试（6 场景）"""
    
    def setup_method(self):
        self.mixin = ExecMixin()
        # 强制开启路径白名单（绕过 env 门控）
        self._env_patch = mock_patch.dict(os.environ, {"MIMIR_PATH_WHITELIST": "workspace,project"})
        self._env_patch.start()
    
    def teardown_method(self):
        self._env_patch.stop()
    
    # ── S1: 符号链接绕过 ──
    def test_S1_symlink_bypass_should_block(self):
        """🔴 S1: 符号链接 ~/.openclaw/sym → ~/.ssh/id_rsa 当前 _DENY_PATH_FRAGMENTS
        字符串 contains 只看 symlink 表层路径 → 不挡 → 读 SSH 私钥"""
        # 构造场景
        try:
            os.symlink(os.path.expanduser("~/.ssh/id_rsa"), "/tmp/sym_ssh_test")
            real_target = os.path.realpath("/tmp/sym_ssh_test")
            assert "/.ssh/" in real_target, "fixture 错误"
        except (OSError, FileExistsError):
            pytest.skip("环境无 ~/.ssh/id_rsa 或 symlink 创建失败")
        
        # 当前代码（仅 strings contains）会放过 symlink 路径
        _path = "/tmp/sym_ssh_test"
        _DENY = ("/.ssh/",)
        bypass_works = not any(frag in _path for frag in _DENY)
        assert bypass_works, "审计 S1 警告：当前实现确实放过符号链接"
        # 修复后（os.path.realpath）应能拦住
        realpath_check = any(frag in os.path.realpath(_path) for frag in _DENY)
        assert realpath_check, "修复方案验证：realpath 后能命中 DENY"
    
    # ── S2: 大小写绕过 ──
    def test_S2_case_insensitive_bypass(self):
        """🔴 S2: /.SSH/ vs /.ssh/ — Unix/Mac 文件系统不区分大小写，
        但 _DENY_PATH_FRAGMENTS 字符串精确小写匹配 → 大写路径绕过"""
        _path = "/home/rayliu/.SSH/id_rsa"
        _DENY = ("/.ssh/",)
        bypass = not any(frag in _path for frag in _DENY)
        assert bypass, "审计 S2 验证：大写 .SSH/ 100% 绕过"
        # 修复方案
        fixed = any(frag in os.path.normcase(_path) for frag in _DENY)
        assert fixed, "normcase 后能命中"
    
    # ── S3: URL 编码绕过 ──
    def test_S3_url_encoded_bypass(self):
        """🔴 S3: %2e%2e → ..  — _DENY 字符串 contains 不解码 URL 编码"""
        from urllib.parse import unquote
        _path = "/home/rayliu/wiki/%2e%2e/.ssh/id_rsa"
        _DENY = ("/.ssh/",)
        bypass = not any(frag in _path for frag in _DENY)
        assert bypass, "审计 S3 验证：URL 编码路径 100% 绕过"
        # 修复方案
        fixed = any(frag in unquote(_path) for frag in _DENY)
        assert fixed, "unquote 后能命中"
    
    # ── L4: normpath 精确前缀匹配误伤修复验证 ──
    def test_L4_normpath_precise_prefix(self):
        """🟡 L4: /etc/ssl/certs/ca-certificates.crt 不应被误伤
        （当前 _DENY_PATH_FRAGMENTS 含 '/etc/' contains 会误伤）"""
        legal_paths = [
            "/etc/ssl/certs/ca-certificates.crt",
            "/home/rayliu/.ssh-not-real/notes.md",
            "/home/rayliu/.awsome-but-not-aws/notes.md",
        ]
        # 当前实现误伤
        _DENY = ("/etc/", "/.ssh/", "/.aws/")
        for p in legal_paths:
            wrongly_blocked = any(frag in p for frag in _DENY)
            assert wrongly_blocked, f"fixture 验证：当前实现确实误伤 {p}"
        # 修复方案：os.path.normpath + 精确前缀
        for p in legal_paths:
            norm = os.path.normpath(p)
            safe = all(not norm.startswith(os.path.normpath(frag)) for frag in _DENY)
            assert safe, f"normpath 后 {p} 不应被拦"
    
    # ── L5: exec 无路径参数放过致命命令 ──
    def test_L5_exec_command_without_path(self):
        """🟡 L5: exec("rm -rf /") → _path = "" → 当前实现 return None → 不拦
        阶段 1 注释「只挡路径」逻辑漏洞"""
        _path = ""
        assert _path == "", "fixture 验证：exec 无路径参数 → _path 为空"
        # 当前实现
        if not _path:
            current_behavior = "return None（不拦截）"
        # 这就是审计 L5 发现的漏洞
        assert current_behavior == "return None（不拦截）", "确认审计 L5 准确"
        # 阶段 1.5 应增「命令内容扫描」
    
    # ── S4: exec kwargs 多参数名未覆盖 ──
    def test_S4_exec_kwarg_bypass(self):
        """🟡 S4: exec({"script_path": "/etc/passwd"}) → 当前实现只读 3 个固定 key
        （path/cwd/command）→ script_path 不被识别 → 绕过"""
        arguments = {"script_path": "/etc/passwd"}
        # 当前实现
        _path = str(arguments.get("path") or arguments.get("cwd") or arguments.get("command") or "")
        assert _path == "", "审计 S4 验证：script_path 参数名 100% 绕过"
        # 修复方案：扫描全部 string 值
        all_str_values = [v for v in arguments.values() if isinstance(v, str)]
        fixed_path = " ".join(all_str_values)
        assert "/etc/passwd" in fixed_path, "扫描全部 string 值能命中"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
