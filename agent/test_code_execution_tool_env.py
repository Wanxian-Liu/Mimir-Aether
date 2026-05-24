import json
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _force_local_terminal_env(monkeypatch):
    """Parity tests exercise the UDS local sandbox; honor host TERMINAL_ENV otherwise."""
    monkeypatch.setenv("TERMINAL_ENV", "local")


def _run_execute_code(code: str) -> dict:
    # Import inside helper so module-level imports don't break test collection.
    from tools.code_execution_tool import execute_code

    out = execute_code(code=code)
    return json.loads(out)


def test_execute_code_home_overrides_when_profile_dir_exists(tmp_path, monkeypatch):
    import tools.code_execution_tool as cet

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))

    profile_home = tmp_path / "home"

    # Case 1: directory exists => HOME should be overridden to profile_home.
    profile_home.mkdir(parents=True, exist_ok=True)
    code = "import os; print(os.environ.get('HOME','').strip())"
    res1 = _run_execute_code(code)
    assert res1.get("status") in ("success", "error")
    output1 = (res1.get("output") or "").strip()
    assert output1 == str(profile_home)

    # Case 2: directory missing => HOME should NOT be overridden.
    for p in sorted(profile_home.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
    for p in sorted(profile_home.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass
    try:
        profile_home.rmdir()
    except OSError:
        pass

    res2 = _run_execute_code(code)
    output2 = (res2.get("output") or "").strip()
    assert output2 != str(profile_home)


def test_execute_code_child_env_strips_secret_like_vars(monkeypatch, tmp_path):
    """Sandbox child must not inherit parent env vars whose names look like credentials."""
    import tools.code_execution_tool as cet

    secret_key = "ZZ_MIMIR_PARITY_EXEC_ENV_API_KEY"
    secret_token = "ZZ_MIMIR_PARITY_EXEC_ENV_SESSION_TOKEN"
    nonsafe_plain = "ZZ_MIMIR_PARITY_EXEC_ENV_PLAIN_UNTRUSTED"
    sentinel = "parity-exec-env-never-in-child"

    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv(secret_key, sentinel)
    monkeypatch.setenv(secret_token, sentinel)
    monkeypatch.setenv(nonsafe_plain, sentinel)

    probe = r"""
import json, os
print(json.dumps({
    "api_key": os.environ.get(%r),
    "token": os.environ.get(%r),
    "plain": os.environ.get(%r),
    "path_ok": "PATH" in os.environ,
}, sort_keys=True))
""" % (secret_key, secret_token, nonsafe_plain)

    res = _run_execute_code(probe.strip())
    assert res.get("status") in ("success", "error")
    inner = json.loads((res.get("output") or "").strip())
    assert inner.get("api_key") is None
    assert inner.get("token") is None
    assert inner.get("plain") is None
    assert inner.get("path_ok") is True
    blob = (res.get("output") or "") + (res.get("error") or "")
    assert sentinel not in blob


def test_execute_code_child_env_passthrough_via_skill_registry(monkeypatch, tmp_path):
    """Skill/session allowlist must pass secret-like names through before stripping."""
    import tools.code_execution_tool as cet
    from tools import env_passthrough as ep

    var = "ZZ_MIMIR_PARITY_REGISTRY_PASSTHROUGH_API_KEY"
    sentinel = "registry-passthrough-ok-a1b2"
    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv(var, sentinel)
    ep.register_env_passthrough([var])
    try:
        probe = (
            "import json, os; print(json.dumps({"
            f"'v': os.environ.get({var!r})"
            "}))"
        )
        res = _run_execute_code(probe)
        assert res.get("status") in ("success", "error")
        inner = json.loads((res.get("output") or "").strip())
        assert inner.get("v") == sentinel
    finally:
        ep.clear_env_passthrough()


def test_execute_code_passthrough_does_not_leak_other_secrets(monkeypatch, tmp_path):
    """Registering one KEY-like var must not pass any other KEY-like parent env vars."""
    import tools.code_execution_tool as cet
    from tools import env_passthrough as ep

    allowed = "ZZ_MIMIR_PARITY_COMBO_ALLOWED_API_KEY"
    blocked = "ZZ_MIMIR_PARITY_COMBO_BLOCKED_API_KEY"
    val_allowed = "combo-allowed-only"
    val_blocked = "combo-must-not-appear-in-child"
    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv(allowed, val_allowed)
    monkeypatch.setenv(blocked, val_blocked)
    ep.register_env_passthrough([allowed])
    try:
        probe = (
            "import json, os; print(json.dumps({"
            f"'a': os.environ.get({allowed!r}), "
            f"'b': os.environ.get({blocked!r})"
            "}, sort_keys=True))"
        )
        res = _run_execute_code(probe)
        assert res.get("status") in ("success", "error")
        inner = json.loads((res.get("output") or "").strip())
        assert inner.get("a") == val_allowed
        assert inner.get("b") is None
        blob = (res.get("output") or "") + (res.get("error") or "")
        assert val_blocked not in blob
    finally:
        ep.clear_env_passthrough()


def test_execute_code_child_env_passthrough_via_config_yaml(monkeypatch, tmp_path):
    """terminal.env_passthrough in config.yaml must allow named vars into the child."""
    import tools.code_execution_tool as cet
    from tools import env_passthrough as ep

    var = "ZZ_MIMIR_PARITY_YAML_PASSTHROUGH_API_KEY"
    sentinel = "yaml-passthrough-ok-c3d4"
    cfg_root = tmp_path / "profile" / "mimir-aether"
    cfg_root.mkdir(parents=True)
    (cfg_root / "config.yaml").write_text(
        "terminal:\n  env_passthrough:\n    - %s\n" % var,
        encoding="utf-8",
    )

    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    # Canonical project home (takes precedence over legacy MIMIRAETHER_HOME).
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(cfg_root))
    monkeypatch.setenv(var, sentinel)
    ep._config_passthrough = None  # force reload from temp config

    try:
        probe = (
            "import json, os; print(json.dumps({"
            f"'v': os.environ.get({var!r})"
            "}))"
        )
        res = _run_execute_code(probe)
        assert res.get("status") in ("success", "error")
        inner = json.loads((res.get("output") or "").strip())
        assert inner.get("v") == sentinel
    finally:
        ep._config_passthrough = None


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="local execute_code uses UDS; not available on Windows",
)
def test_execute_code_child_pythonpath_includes_repo_root_first(monkeypatch, tmp_path):
    """Local sandbox prepends repo root so `import tools` works in the child."""
    import tools.code_execution_tool as cet

    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    root = os.path.dirname(os.path.dirname(os.path.abspath(cet.__file__)))

    probe = """
import json, os
ok = False
try:
    import tools as _tools  # noqa: F401
    ok = True
except ImportError:
    ok = False
raw = os.environ.get("PYTHONPATH") or ""
parts = [p for p in raw.split(os.pathsep) if p != ""]
print(json.dumps({"import_tools": ok, "first": parts[0] if parts else None}))
"""
    res = _run_execute_code(probe.strip())
    assert res.get("status") in ("success", "error")
    inner = json.loads((res.get("output") or "").strip())
    assert inner.get("import_tools") is True
    assert inner.get("first") == root


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="local execute_code uses UDS; not available on Windows",
)
def test_execute_code_child_pythonpath_prepends_repo(monkeypatch, tmp_path):
    """Parent PYTHONPATH entries are kept after the repo root (pathsep order)."""
    import tools.code_execution_tool as cet

    monkeypatch.setattr(cet.Path, "home", staticmethod(lambda: tmp_path))
    root = os.path.dirname(os.path.dirname(os.path.abspath(cet.__file__)))
    extra = str(tmp_path / "extra_pp_entry")
    monkeypatch.setenv("PYTHONPATH", extra)

    probe = """
import json, os
raw = os.environ.get("PYTHONPATH") or ""
parts = [p for p in raw.split(os.pathsep) if p != ""]
print(json.dumps({"parts": parts}))
"""
    res = _run_execute_code(probe.strip())
    assert res.get("status") in ("success", "error")
    inner = json.loads((res.get("output") or "").strip())
    parts = inner.get("parts") or []
    assert len(parts) >= 2
    assert parts[0] == root
    assert extra in parts

