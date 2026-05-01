"""Mocked coverage for execute_code remote backend (no real Docker/SSH/Modal)."""

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import model_tools

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="execute_code is disabled on Windows before remote/local split",
)


class FilesystemEmulatingEnv:
    """Execute shell-like commands by mutating a real directory tree (for remote tests)."""

    def __init__(self, tmp_root: Path):
        self._tmp = tmp_root.resolve()

    def get_temp_dir(self) -> str:
        return str(self._tmp)

    def execute(self, cmd, cwd="/", timeout=30):
        if "command -v python3" in cmd:
            return {"output": "OK\n", "returncode": 0}
        if cmd.startswith("mkdir -p"):
            target = shlex.split(cmd)[2]
            Path(target).mkdir(parents=True, exist_ok=True)
            return {"output": "", "returncode": 0}
        if " && mv " in cmd and "base64 -d >" in cmd:
            return self._echo_base64_then_mv(cmd)
        if "echo '" in cmd and "base64 -d >" in cmd:
            return self._echo_base64_ship(cmd)
        if "ls -1 " in cmd and "/req_" in cmd:
            return self._ls_req(cmd)
        if cmd.startswith("cat "):
            path = shlex.split(cmd)[1]
            text = Path(path).read_text(encoding="utf-8")
            return {"output": text, "returncode": 0}
        if cmd.startswith("rm -f "):
            parts = shlex.split(cmd)
            path = parts[-1]
            Path(path).unlink(missing_ok=True)
            return {"output": "", "returncode": 0}
        if "python3 script.py" in cmd:
            return self._run_user_script(cmd, timeout)
        if cmd.startswith("rm -rf "):
            path = shlex.split(cmd)[1]
            p = Path(path)
            if p.exists():
                shutil.rmtree(p)
            return {"output": "", "returncode": 0}
        raise AssertionError(f"unexpected remote cmd: {cmd[:220]!r}")

    @staticmethod
    def _echo_base64_ship(cmd: str):
        left, _, right = cmd.partition(" | base64 -d > ")
        if not left.startswith("echo '"):
            raise AssertionError(f"expected echo '…': {left[:80]!r}")
        b64 = left[6:-1]
        dest = shlex.split(right)[0]
        raw = base64.b64decode(b64.encode("ascii"))
        d = Path(dest)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(raw)
        return {"output": "", "returncode": 0}

    def _echo_base64_then_mv(self, cmd: str):
        first, _, mv_rest = cmd.partition(" && mv ")
        self._echo_base64_ship(first)
        parts = shlex.split(mv_rest)
        if len(parts) >= 2:
            shutil.move(parts[0], parts[1])
        return {"output": "", "returncode": 0}

    @staticmethod
    def _ls_req(cmd: str):
        # cmd like: ls -1 '/tmp/.../rpc'/req_* 2>/dev/null || true
        if "/req_*" not in cmd:
            raise AssertionError(f"cannot parse ls req cmd: {cmd!r}")
        before = cmd.split("/req_*", 1)[0]
        _, _, tail = before.partition("ls -1 ")
        rpc_dir = shlex.split(tail.strip())[0]
        rpc = Path(rpc_dir)
        if not rpc.is_dir():
            return {"output": "", "returncode": 0}
        paths = sorted(
            p for p in rpc.glob("req_*")
            if p.is_file() and not p.name.endswith(".tmp")
        )
        body = "\n".join(str(p) for p in paths)
        return {"output": body + ("\n" if body else ""), "returncode": 0}

    def _run_user_script(self, cmd: str, timeout: float):
        cd_part, _, rest = cmd.partition(" && ")
        sandbox = Path(shlex.split(cd_part)[1])
        rpc = sandbox / "rpc"
        env = os.environ.copy()
        env["HERMES_RPC_DIR"] = str(rpc)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if " TZ=" in rest or rest.startswith("TZ="):
            for token in shlex.split(rest):
                if token.startswith("TZ="):
                    env["TZ"] = token.split("=", 1)[1]
                    break
        proc = subprocess.run(
            [sys.executable, "script.py"],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            env=env,
            timeout=min(float(timeout), 120.0),
        )
        out = proc.stdout
        if proc.stderr:
            out += "\n--- stderr ---\n" + proc.stderr
        return {"output": out, "returncode": proc.returncode}


def test_execute_remote_returns_error_when_python3_not_on_path(monkeypatch):
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class FakeEnv:
        def execute(self, cmd, cwd="/", timeout=30):
            if "command -v python3" in cmd:
                # No python3 → no "OK" line (same as real shell short-circuit).
                return {"output": "", "returncode": 0}
            raise AssertionError(
                "remote execute_code should early-return before any other "
                f"remote command; got: {cmd[:120]!r}"
            )

    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(cet, "_get_or_create_env", lambda _tid: (FakeEnv(), "docker"))

    raw = cet.execute_code("print('noop')")
    data = json.loads(raw)
    assert data.get("status") == "error"
    assert data.get("tool_calls_made") == 0
    err = data.get("error") or ""
    assert "Python 3" in err
    assert "docker" in err.lower()


def test_execute_remote_minimal_success_mocked_env(monkeypatch):
    """Happy path: python3 OK → mkdir → ship stubs → run script → cleanup (RPC idle)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class FakeEnvRemoteSuccess:
        def execute(self, cmd, cwd="/", timeout=30):
            if "command -v python3" in cmd:
                return {"output": "OK\n", "returncode": 0}
            if cmd.startswith("mkdir -p"):
                return {"output": "", "returncode": 0}
            if "echo '" in cmd and "base64 -d >" in cmd:
                return {"output": "", "returncode": 0}
            if "ls -1 " in cmd and "/req_" in cmd:
                return {"output": "", "returncode": 0}
            if "python3 script.py" in cmd:
                return {"output": "remote-sandbox-stdout\n", "returncode": 0}
            if cmd.startswith("rm -rf "):
                return {"output": "", "returncode": 0}
            raise AssertionError(f"unexpected remote cmd fragment: {cmd[:160]!r}")

    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(cet, "_get_or_create_env", lambda _tid: (FakeEnvRemoteSuccess(), "docker"))

    raw = cet.execute_code("print('from-user-code')")
    data = json.loads(raw)
    assert data.get("status") == "success"
    assert data.get("tool_calls_made") == 0
    out = data.get("output") or ""
    assert "remote-sandbox-stdout" in out


def test_execute_remote_script_timeout_exit_124(monkeypatch):
    """Backend uses exit 124 for timeout (e.g. GNU timeout); map to status=timeout."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class FakeEnvTimeout124:
        def execute(self, cmd, cwd="/", timeout=30):
            if "command -v python3" in cmd:
                return {"output": "OK\n", "returncode": 0}
            if cmd.startswith("mkdir -p"):
                return {"output": "", "returncode": 0}
            if "echo '" in cmd and "base64 -d >" in cmd:
                return {"output": "", "returncode": 0}
            if "ls -1 " in cmd and "/req_" in cmd:
                return {"output": "", "returncode": 0}
            if "python3 script.py" in cmd:
                return {"output": "partial-before-kill\n", "returncode": 124}
            if cmd.startswith("rm -rf "):
                return {"output": "", "returncode": 0}
            raise AssertionError(f"unexpected remote cmd fragment: {cmd[:160]!r}")

    monkeypatch.setattr(cet, "_load_config", lambda: {"timeout": 77, "max_tool_calls": 50})
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(cet, "_get_or_create_env", lambda _tid: (FakeEnvTimeout124(), "docker"))

    raw = cet.execute_code("print('x')")
    data = json.loads(raw)
    assert data.get("status") == "timeout"
    assert data.get("tool_calls_made") == 0
    err = (data.get("error") or "").lower()
    assert "timed out" in err
    assert "77" in (data.get("error") or "")
    out = data.get("output") or ""
    assert "partial-before-kill" in out


def test_execute_remote_script_interrupt_exit_130(monkeypatch):
    """Backend exit 130 (SIGINT-style) maps to status=interrupted."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class FakeEnvInterrupt130:
        def execute(self, cmd, cwd="/", timeout=30):
            if "command -v python3" in cmd:
                return {"output": "OK\n", "returncode": 0}
            if cmd.startswith("mkdir -p"):
                return {"output": "", "returncode": 0}
            if "echo '" in cmd and "base64 -d >" in cmd:
                return {"output": "", "returncode": 0}
            if "ls -1 " in cmd and "/req_" in cmd:
                return {"output": "", "returncode": 0}
            if "python3 script.py" in cmd:
                return {"output": "before-interrupt\n", "returncode": 130}
            if cmd.startswith("rm -rf "):
                return {"output": "", "returncode": 0}
            raise AssertionError(f"unexpected remote cmd fragment: {cmd[:160]!r}")

    monkeypatch.setattr(cet, "_load_config", lambda: {"timeout": 60, "max_tool_calls": 50})
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(cet, "_get_or_create_env", lambda _tid: (FakeEnvInterrupt130(), "docker"))

    raw = cet.execute_code("print('x')")
    data = json.loads(raw)
    assert data.get("status") == "interrupted"
    assert data.get("tool_calls_made") == 0
    assert data.get("error") is None
    out = data.get("output") or ""
    assert "before-interrupt" in out
    assert "execution interrupted" in out.lower()


def test_execute_remote_dispatches_tool_via_file_rpc(monkeypatch, tmp_path):
    """RPC poll loop serves one web_search request (real child + real req/res files)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "a" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"parity_stub": True, "tool": name})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
r = hermes_tools.web_search("parity-remote-q", 2)
print("TOOL_RET", r)
"""
    raw = cet.execute_code(code, enabled_tools=["web_search"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "TOOL_RET" in out
    assert "parity_stub" in out
    assert dispatched == [
        ("web_search", {"query": "parity-remote-q", "limit": 2}),
    ]


def test_execute_remote_malformed_req_json_is_removed_and_rpc_continues(
    monkeypatch, tmp_path,
):
    """Garbage req_* (before real stub seq) is deleted; valid web_search still runs."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "e" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"after_bad_req": True})

    root = tmp_path.resolve()
    rpc_dir = root / "hermes_exec_eeeeeeeeeeee" / "rpc"
    rpc_dir.mkdir(parents=True)
    bad_req = rpc_dir / "req_000000"
    bad_req.write_text("{{{not_valid_json_for_rpc", encoding="utf-8")

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
print("TOOL_RET", hermes_tools.web_search("after-garbage-req", 1))
"""
    raw = cet.execute_code(code, enabled_tools=["web_search"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    assert "TOOL_RET" in (data.get("output") or "")
    assert "after_bad_req" in (data.get("output") or "")
    assert dispatched == [
        ("web_search", {"query": "after-garbage-req", "limit": 1}),
    ]
    assert not bad_req.exists()


def test_execute_remote_read_file_tool_via_file_rpc(monkeypatch, tmp_path):
    """Non-web sandbox tool: read_file over file-based RPC (stubbed handler)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "f" * 32

    target = (tmp_path / "rpc_read_target.txt").resolve()
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"content": "stub-body", "total_lines": 2, "truncated": False})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = f"""import hermes_tools
print("RF", hermes_tools.read_file({str(target)!r}, 1, 5))
"""
    raw = cet.execute_code(code, enabled_tools=["read_file"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "RF" in out
    assert "stub-body" in out
    assert len(dispatched) == 1
    assert dispatched[0][0] == "read_file"
    assert dispatched[0][1]["path"] == str(target)
    assert dispatched[0][1]["offset"] == 1
    assert dispatched[0][1]["limit"] == 5


def test_execute_remote_terminal_tool_via_file_rpc(monkeypatch, tmp_path):
    """Non-web sandbox tool: terminal() over file-based RPC (stubbed handler)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "1" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"output": "parity-term-stub\n", "exit_code": 0})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
print("TM", hermes_tools.terminal("echo noop", 99, None))
"""
    raw = cet.execute_code(code, enabled_tools=["terminal"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "TM" in out
    assert "parity-term-stub" in out
    assert len(dispatched) == 1
    assert dispatched[0][0] == "terminal"
    args = dispatched[0][1]
    assert args["command"] == "echo noop"
    assert args.get("timeout") == 99
    assert args.get("workdir") is None or args.get("workdir") == ""


def test_execute_remote_web_extract_tool_via_file_rpc(monkeypatch, tmp_path):
    """web_extract over file-based RPC (stubbed handler)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "2" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"results": [{"url": "stub", "content": "x"}]})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
print("WX", hermes_tools.web_extract(["https://example.invalid/parity-wx"]))
"""
    raw = cet.execute_code(code, enabled_tools=["web_extract"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "WX" in out and "stub" in out
    assert len(dispatched) == 1
    assert dispatched[0][0] == "web_extract"
    assert dispatched[0][1]["urls"] == ["https://example.invalid/parity-wx"]


def test_execute_remote_patch_tool_via_file_rpc(monkeypatch, tmp_path):
    """patch(mode=replace) over file-based RPC (stubbed handler)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "3" * 32

    patch_file = (tmp_path / "rpc_patch_target.txt").resolve()
    patch_file.write_text("before OLD after\n", encoding="utf-8")

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"success": True, "stub": True})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = f"""import hermes_tools
print("PC", hermes_tools.patch(
    path={str(patch_file)!r},
    old_string="OLD",
    new_string="NEW",
    replace_all=False,
    mode="replace",
    patch=None,
))
"""
    raw = cet.execute_code(code, enabled_tools=["patch"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "PC" in out and "stub" in out.lower()
    assert len(dispatched) == 1
    assert dispatched[0][0] == "patch"
    a = dispatched[0][1]
    assert a["path"] == str(patch_file)
    assert a["old_string"] == "OLD"
    assert a["new_string"] == "NEW"
    assert a.get("replace_all") in (False, 0)
    assert a.get("mode") == "replace"


def test_execute_remote_search_files_tool_via_file_rpc(monkeypatch, tmp_path):
    """search_files over file-based RPC (stubbed handler)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "4" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"matches": [{"path": "stub-match", "line": 1}]})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
print("SF", hermes_tools.search_files(
    pattern="parityneedle",
    target="content",
    path=".",
    file_glob="*.md",
    limit=7,
    offset=0,
    output_mode="content",
    context=1,
))
"""
    raw = cet.execute_code(code, enabled_tools=["search_files"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "SF" in out and "stub-match" in out
    assert len(dispatched) == 1
    assert dispatched[0][0] == "search_files"
    a = dispatched[0][1]
    assert a["pattern"] == "parityneedle"
    assert a.get("target") == "content"
    assert a.get("path") == "."
    assert a.get("file_glob") == "*.md"
    assert a.get("limit") == 7
    assert a.get("offset") == 0
    assert a.get("output_mode") == "content"
    assert a.get("context") == 1


def test_execute_remote_two_distinct_tools_in_one_script(monkeypatch, tmp_path):
    """One execute_code run: web_search + read_file (different RPC tools)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "5" * 32

    target = (tmp_path / "multi_tool_read.txt").resolve()
    target.write_text("multi\n", encoding="utf-8")

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        if name == "web_search":
            return json.dumps({"ok": "search"})
        if name == "read_file":
            return json.dumps({"content": "multi-tool-read-stub", "total_lines": 1})
        raise AssertionError(name)

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = f"""import hermes_tools
print("W", hermes_tools.web_search("multi-q", 2))
print("R", hermes_tools.read_file({str(target)!r}, 1, 10))
"""
    raw = cet.execute_code(code, enabled_tools=["web_search", "read_file"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 2
    out = data.get("output") or ""
    assert "search" in out.lower() or "ok" in out.lower()
    assert "multi-tool-read-stub" in out
    assert [d[0] for d in dispatched] == ["web_search", "read_file"]
    assert dispatched[0][1]["query"] == "multi-q"
    assert dispatched[1][1]["path"] == str(target)


def test_execute_remote_three_distinct_tools_in_one_script(monkeypatch, tmp_path):
    """One execute_code run: web_search + read_file + web_extract (Tier-0 matrix B)."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "7" * 32

    target = (tmp_path / "triple_read.txt").resolve()
    target.write_text("triple-line\n", encoding="utf-8")

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        if name == "web_search":
            return json.dumps({"ok": "triple-search"})
        if name == "read_file":
            return json.dumps({"content": "triple-read-stub", "total_lines": 1})
        if name == "web_extract":
            return json.dumps({"results": [{"url": "triple-url", "content": "xe"}]})
        raise AssertionError(name)

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = f"""import hermes_tools
print("W", hermes_tools.web_search("triple-q", 3))
print("R", hermes_tools.read_file({str(target)!r}, 1, 10))
print("X", hermes_tools.web_extract(["https://example.invalid/triple-wx"]))
"""
    raw = cet.execute_code(
        code,
        enabled_tools=["web_search", "read_file", "web_extract"],
    )
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 3
    out = data.get("output") or ""
    assert "triple-search" in out or "ok" in out.lower()
    assert "triple-read-stub" in out
    assert "triple-url" in out
    assert [d[0] for d in dispatched] == ["web_search", "read_file", "web_extract"]
    assert dispatched[0][1]["query"] == "triple-q"
    assert dispatched[1][1]["path"] == str(target)
    assert dispatched[2][1]["urls"] == ["https://example.invalid/triple-wx"]


def test_execute_remote_patch_and_terminal_in_one_script(monkeypatch, tmp_path):
    """One execute_code run: patch + terminal in a single remote script."""
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "8" * 32

    patch_file = (tmp_path / "patch_then_term.txt").resolve()
    patch_file.write_text("before OLD after\n", encoding="utf-8")

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        if name == "patch":
            return json.dumps({"success": True, "stub": "patch-ok"})
        if name == "terminal":
            return json.dumps({"output": "terminal-ok\n", "exit_code": 0})
        raise AssertionError(name)

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = f"""import hermes_tools
print("P", hermes_tools.patch({str(patch_file)!r}, "OLD", "NEW"))
print("T", hermes_tools.terminal("echo combo", 30, None))
"""
    raw = cet.execute_code(
        code,
        enabled_tools=["patch", "terminal"],
    )
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 2
    out = data.get("output") or ""
    assert "patch-ok" in out
    assert "terminal-ok" in out
    assert [d[0] for d in dispatched] == ["patch", "terminal"]
    p_args = dispatched[0][1]
    assert p_args["path"] == str(patch_file)
    assert p_args["old_string"] == "OLD"
    assert p_args["new_string"] == "NEW"
    assert p_args.get("mode") == "replace"
    t_args = dispatched[1][1]
    assert t_args["command"] == "echo combo"
    assert t_args.get("timeout") == 30
    assert t_args.get("workdir") is None or t_args.get("workdir") == ""


def test_execute_remote_two_tool_calls_via_file_rpc(monkeypatch, tmp_path):
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "b" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"n": len(dispatched), "tool": name})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
print("A", hermes_tools.web_search("first", 1))
print("B", hermes_tools.web_search("second", 2))
"""
    raw = cet.execute_code(code, enabled_tools=["web_search"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 2
    out = data.get("output") or ""
    assert "'n': 1" in out and "'n': 2" in out
    assert dispatched == [
        ("web_search", {"query": "first", "limit": 1}),
        ("web_search", {"query": "second", "limit": 2}),
    ]


def test_execute_remote_max_tool_calls_blocks_second_rpc(monkeypatch, tmp_path):
    import tools.code_execution_tool as cet
    from tools import terminal_tool as tt

    class _FixedUUID:
        hex = "c" * 32

    dispatched: list[tuple[str, dict]] = []

    def fake_handle(name, args, task_id=None):
        dispatched.append((name, dict(args)))
        return json.dumps({"ok": True})

    monkeypatch.setattr(model_tools, "handle_function_call", fake_handle)
    monkeypatch.setattr(cet, "_load_config", lambda: {"max_tool_calls": 1, "timeout": 120})
    monkeypatch.setattr(cet.uuid, "uuid4", lambda: _FixedUUID())
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "docker"})
    monkeypatch.setattr(
        cet,
        "_get_or_create_env",
        lambda _tid: (FilesystemEmulatingEnv(tmp_path), "docker"),
    )

    code = """import hermes_tools
import json
r1 = hermes_tools.web_search("once", 1)
r2 = hermes_tools.web_search("twice", 1)
print("R1", r1)
print("R2", r2)
"""
    raw = cet.execute_code(code, enabled_tools=["web_search"])
    data = json.loads(raw)
    assert data.get("status") == "success", data
    assert data.get("tool_calls_made") == 1
    out = data.get("output") or ""
    assert "R1" in out and "ok" in out.lower()
    assert "R2" in out
    assert "limit" in out.lower() or "Tool call limit" in out
    assert len(dispatched) == 1
