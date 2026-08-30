#!/usr/bin/env python3
"""P0-1 delegate兜底验证 — 独立进程真实 delegate 测试（新代码路径）。

构造模拟 MimirAetherAgent 的 mock parent（无 base_url / providers_* 属性），
调用真实 delegate_task 单任务模式，确认：
1. 不抛 AttributeError（修复前 L347 parent_agent.base_url 裸访问必炸）
2. 子代理正常返回结果
"""
import json
import os
import sys
import traceback

sys.path.insert(0, "/home/rayliu/src/MimirAether")

# 加载 ~/.mimiraether/.env 到进程 env（不打印任何 key 值）
_env_path = os.path.expanduser("~/.mimiraether/.env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


class MockMimirParent:
    """模拟 MimirAetherAgent：有核心属性，但故意没有 base_url/providers_*（修复点）。"""

    def __init__(self):
        self.model = "deepseek/deepseek-v4-flash"
        self.provider = "deepseek"
        self.api_key = None  # 由 delegation creds 解析覆盖
        self.api_mode = "chat"
        self.acp_command = None
        self.acp_args = []
        self.max_tokens = 1024
        self.prefill_messages = None
        self.session_id = "p0-1-smoke-session"
        self._session_db = None
        self.platform = "cli"
        self.enabled_toolsets = []
        self.valid_tool_names = []
        self._active_children = []
        self._delegate_depth = 0
        self.reasoning_config = None
        self.tool_progress_callback = None
        self._subdirectory_hints = None
        self.terminal_cwd = None
        self.cwd = None
        self._client_kwargs = {}

    def _memory_manager(self):
        return None

    @property
    def _memory_manager(self):
        return None


def main():
    from tools.delegate_tool import delegate_task

    parent = MockMimirParent()
    # 断言 mock 确实没有修复点属性（模拟 MimirAetherAgent 的接口缺失）
    missing = [a for a in ("base_url", "providers_allowed", "providers_ignored",
                           "providers_order", "provider_sort") if hasattr(parent, a)]
    if missing:
        print(f"FAIL: mock 意外包含属性 {missing}，测试无效")
        sys.exit(1)
    print("mock parent 无 base_url/providers_* 属性 —— 与 MimirAetherAgent 接口一致")

    try:
        result = delegate_task(
            goal="只回复『delegate smoke OK』，不要调用任何工具。",
            max_iterations=1,
            parent_agent=parent,
        )
        print("=== delegate_task 返回 ===")
        print(result[:2000])
        try:
            parsed = json.loads(result)
            r0 = parsed.get("results", [{}])[0]
            ok = r0.get("status") == "completed"  # delegate 返回 status 而非 success
            print(f"=== 解析: status={r0.get('status')} summary={r0.get('summary')} ===")
        except json.JSONDecodeError:
            print("=== 返回非 JSON（可能为错误消息），原样展示 ===")
        print("RESULT_MARKER: NO_ATTRIBUTE_ERROR" if "AttributeError" not in result
              else "RESULT_MARKER: STILL_HAS_ATTRIBUTE_ERROR")
    except AttributeError as exc:
        print(f"FAIL: AttributeError 仍存在 -> {exc}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as exc:
        print(f"其他异常（非 AttributeError）: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
