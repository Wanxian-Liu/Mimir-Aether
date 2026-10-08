"""F2-c guard: gateway/run.py:main() must cap the default-executor join at 5s.

RED before the F2-c patch (main() used a bare asyncio.run(), i.e. a 300s join).
"""
import ast
from pathlib import Path

RUN_PY = Path(__file__).resolve().parents[1] / "gateway" / "run.py"


def _main_src():
    tree = ast.parse(RUN_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return ast.unparse(node)
    raise AssertionError("main() not found in gateway/run.py")


def test_main_has_no_bare_asyncio_run():
    assert "asyncio.run(" not in _main_src()


def test_main_caps_executor_join_at_5s():
    tree = ast.parse(RUN_PY.read_text(encoding="utf-8"))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "shutdown_default_executor"
    ]
    assert len(calls) == 1, "expected exactly one shutdown_default_executor call"
    assert len(calls[0].args) == 1, "timeout must be passed positionally"
    assert isinstance(calls[0].args[0], ast.Constant), "timeout must be a constant"
    assert calls[0].args[0].value == 5.0


def test_main_keeps_the_other_two_closing_steps():
    src = _main_src()
    assert "_cancel_all_tasks" in src
    assert "shutdown_asyncgens" in src
