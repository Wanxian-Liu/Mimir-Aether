"""post_restart_verify: the two false readings this instrument produced.

Both bugs shipped inside the *verifier*, not the thing it verifies:
  * a traceback body (no timestamp) sorted above the start stamp by plain
    string compare ('I' > '2') -> false FAIL=47 on 2026-09-28;
  * the systemd `%Z` stamp was forced to UTC then converted to local (+8h)
    -> empty scope -> false PASS.
"""
import datetime
import importlib.util
import pathlib

SPEC = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "post_restart_verify.py"


def _load():
    spec = importlib.util.spec_from_file_location("prv_under_test", SPEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STAMPED = "2026-09-27 18:14:22,100 ERROR x: RuntimeError: Event loop is closed"
BODY = "ImportError: sys.meta_path is None, Python is likely shutting down"
NEW = "2026-09-28 00:34:13,198 INFO y: ok"


def test_opens_record_only_for_timestamped_lines():
    m = _load()
    assert m._opens_record(STAMPED) is True
    assert m._opens_record(NEW) is True
    assert m._opens_record(BODY) is False
    assert m._opens_record("  File \"/x/y.py\", line 3, in f") is False


def test_body_inherits_parent_record_scope():
    m = _load()
    sc, mode = m.in_scope([STAMPED, BODY, NEW], "2026-09-28 00:00:00")
    assert mode == "since-start"
    assert sc == [NEW]


def test_plain_prefix_compare_is_the_trap():
    """Documents the defect: the body sorts above the stamp, hence the lie."""
    assert BODY[:19] >= "2026-09-28 00:00:00"


def test_empty_scope_after_uptime_is_fail_not_pass(monkeypatch):
    m = _load()
    ten_min_ago = datetime.datetime.now() - datetime.timedelta(minutes=10)
    # NB: strftime("%Z") is empty for a NAIVE datetime -> would take the
    # tail-400 fallback instead of the since-start window.
    stamp = ten_min_ago.strftime("%a %Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(m, "sc", lambda prop: stamp if prop == "ExecMainStartTimestamp" else "")
    monkeypatch.setattr(m, "log_lines", lambda name: [])
    m.fails.clear()
    m.warns.clear()
    row = m.check_cascade()
    assert m.fails, row
    assert "empty-scope" in m.fails[0]


def test_cascade_counter_sees_a_real_burst(monkeypatch):
    """Positive control: boundary before the burst -> the counter must fire.

    Without this arm a zero would be indistinguishable from a blind counter.
    """
    m = _load()
    monkeypatch.setattr(m, "sc", lambda prop: "Mon 2026-09-27 18:00:00 CST")
    monkeypatch.setattr(m, "log_lines", lambda name: [STAMPED, BODY])
    m.fails.clear()
    m.warns.clear()
    row = m.check_cascade()
    assert any("cascade-since-start" in f for f in m.fails), row
