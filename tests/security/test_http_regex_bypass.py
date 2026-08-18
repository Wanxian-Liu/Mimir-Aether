"""
B4 HTTP regex 过宽测试（OpenClaw 审计发现·2026-08-18 22:44）

审计定位：
- 函数：_validate_external_content L412-415
- regex: r"HTTP/[12]\.\d\s+\d{3}"
- 问题：HTTP 404 也命中 → _has_status=True → 不报"无 HTTP 状态信息"

测试矩阵：
1. 验证当前 regex 过宽（404 命中）
2. 验证 200 正常响应命中（regression baseline）
3. 验证 500 错误响应也命中（问题：错误响应被掩盖）
4. 锁定修复期望：regex 收紧到 2xx
5. 验证 JSON 格式的 status_code: 200 命中

测试角色：testing-test-automation-engineer（Loki）
审计来源：OpenClaw 交叉审计段 B4
"""
import re
import pytest


class TestHttpRegexBypass:
    """B4 HTTP regex 过宽验证（OpenClaw 22:44 B4）"""

    # 复制 agent/exec_mixin.py L412-415 的 regex
    _HTTP_STATUS_REGEX = r"HTTP/[12]\.\d\s+\d{3}"
    _JSON_STATUS_REGEX = r"""status[_ ]?code["']?\s*[:=]\s*\d{3}"""

    def _has_http_status(self, content: str) -> bool:
        """复制 _validate_external_content L412-415 的扫描逻辑"""
        return bool(
            re.search(self._HTTP_STATUS_REGEX, content[:2000])
            or re.search(self._JSON_STATUS_REGEX, content[:2000])
        )

    # === Test 1: HTTP 200 正常响应（baseline）===

    def test_http_200_normal_response_matches(self):
        """HTTP/1.1 200 OK → _has_status = True（正确）"""
        content = """HTTP/1.1 200 OK
Content-Type: text/html

<html><body>Hello World</body></html>"""
        assert self._has_http_status(content) is True

    # === Test 2: HTTP 404 错误响应（B4 bug）===

    def test_http_404_error_response_should_not_match(self):
        """HTTP/1.1 404 Not Found → 当前 regex 命中（误判 · B4 bug）"""
        content = """HTTP/1.1 404 Not Found
Content-Type: text/html

<html><body>Page not found</body></html>"""
        # 当前行为：B4 bug → 命中
        assert self._has_http_status(content) is True
        # 锁定 bug：404 被当作格式正确

    def test_http_500_error_response_should_not_match(self):
        """HTTP/1.1 500 Internal Server Error → 当前 regex 命中（误判）"""
        content = """HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{"error": "internal server error"}"""
        assert self._has_http_status(content) is True  # B4 bug

    def test_http_403_forbidden_matches(self):
        """HTTP/1.1 403 Forbidden → 当前 regex 命中（误判）"""
        content = """HTTP/1.1 403 Forbidden
Content-Type: text/plain

Access denied"""
        assert self._has_http_status(content) is True  # B4 bug

    # === Test 3: HTTP/1.0 变体 ===

    def test_http_1_0_404_matches(self):
        """HTTP/1.0 404 Not Found → 当前 regex 命中（误判）"""
        content = """HTTP/1.0 404 Not Found"""
        assert self._has_http_status(content) is True  # B4 bug

    # === Test 4: JSON status_code 格式 ===

    def test_json_status_code_200_matches(self):
        """JSON 格式 status_code: 200 → 命中（正确）"""
        content = """{"status_code": 200, "data": "ok"}"""
        assert self._has_http_status(content) is True

    def test_json_status_code_500_matches(self):
        """JSON 格式 status_code: 500 → 当前 regex 命中（误判）"""
        content = """{"status_code": 500, "error": "internal"}"""
        assert self._has_http_status(content) is True  # B4 bug

    # === Test 5: 修复期望（regex 收紧到 2xx）===

    def test_fix_expectation_2xx_only(self):
        """修复期望：regex 改为只匹配 2xx"""
        _2xx_regex = r"HTTP/[12]\.\d\s+2\d{2}"
        # 200 命中
        assert re.search(_2xx_regex, "HTTP/1.1 200 OK") is not None
        # 404 不命中（修复后）
        assert re.search(_2xx_regex, "HTTP/1.1 404 Not Found") is None
        # 500 不命中（修复后）
        assert re.search(_2xx_regex, "HTTP/1.1 500 Internal Server Error") is None