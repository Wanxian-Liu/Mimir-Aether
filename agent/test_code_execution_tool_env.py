import json
from pathlib import Path

import pytest


def _run_execute_code(code: str) -> dict:
    # Import inside helper so module-level imports don't break test collection.
    from tools.code_execution_tool import execute_code

    out = execute_code(code=code)
    return json.loads(out)


def test_execute_code_home_overrides_when_profile_dir_exists():
    profile_home = Path.home() / ".openclaw" / "mimir-aether"
    existed_before = profile_home.exists()

    # Case 1: directory exists => HOME should be overridden to profile_home.
    profile_home.mkdir(parents=True, exist_ok=True)
    code = "import os; print(os.environ.get('HOME','').strip())"
    res1 = _run_execute_code(code)
    assert res1.get("status") in ("success", "error")
    output1 = (res1.get("output") or "").strip()
    assert output1 == str(profile_home)

    # Case 2: directory missing => HOME should NOT be overridden.
    # To avoid modifying your machine too aggressively, only run this case
    # if the directory did not exist before the test.
    if existed_before:
        pytest.skip("profile_home already exists; skipping missing-directory assertion to avoid side effects")

    # Remove the directory so the override is not applied.
    try:
        for p in sorted(profile_home.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
        for p in sorted(profile_home.rglob("*"), reverse=True):
            if p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
        profile_home.rmdir()
    except FileNotFoundError:
        pass

    code2 = "import os; print(os.environ.get('HOME','').strip())"
    res2 = _run_execute_code(code2)
    output2 = (res2.get("output") or "").strip()
    assert output2 != str(profile_home)

