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


# --- F-2 (#14) memory headroom: cap-vs-peak separation -----------------------
GIB = 1024 ** 3


def test_headroom_old_cap_4g_is_red():
    """Arm A = the ticket's defect: cap glued to the high-water mark."""
    m = _load()
    ok, d = m.memory_headroom(4 * GIB, 4 * GIB, 4 * GIB - 100 * 1024 ** 2)
    assert ok is False, d
    assert d["room_now"] < m.F2_MIN_ROOM_BYTES
    assert d["censored"] is True


def test_headroom_new_cap_6g_is_green():
    """Arm B = the fix: identical peak, cap moved -> room appears."""
    m = _load()
    ok, d = m.memory_headroom(6 * GIB, 4 * GIB, 4227858432)
    assert ok is True, d
    assert d["room_peak"] == 2 * GIB
    assert d["censored"] is True


def test_peak_alone_cannot_decide_the_verdict():
    """Anti-gaming: a LOW peak must not buy a pass while `current` sits at the cap."""
    m = _load()
    ok, d = m.memory_headroom(4 * GIB, 2 * GIB + 12345, 4 * GIB - 100 * 1024 ** 2)
    assert ok is False, d
    assert d["censored"] is False


def test_unbounded_cap_passes():
    m = _load()
    ok, d = m.memory_headroom(None, 4 * GIB, 4 * GIB)
    assert ok is True and d["room_now"] == "inf"


def test_unreadable_cgroup_is_fail_not_pass(monkeypatch):
    """Instrument rule: "no reading" must never be reported as a pass."""
    m = _load()
    monkeypatch.setattr(m, "sc", lambda prop: "/nonexistent-f2-cgroup")
    m.fails.clear()
    m.warns.clear()
    row = m.check_memory_headroom()
    assert m.fails, row
    assert "J6 unreadable" in m.fails[0]


# --- I-4 (2026-10-07): criterion change -> primary cap-vs-peak, fallback 1 GiB ---
# Controlled arms for ``memory_headroom``. Live band at the 6 GiB cap:
# current ~3.82-4.00 GiB  =>  room_now ~2.00-2.18 GiB. The old 2 GiB floor sat
# ON that band, so the same reading flipped red/green with load (I-4).
# The OLD criterion is reproduced by passing the old floor explicitly
# (min_room=2*GIB), so both criteria are compared on identical inputs.
# NB: the ticket listed "current {2.00, 2.10, 2.18} GiB"; those are the
# *room_now* values of its own background section (room_now = cap - current),
# so the sample is expressed as room_now and current is derived: cur = cap - room_now.
# The sub-2.00 sample is required: 2.00/2.10/2.18 alone all sit on the green
# side of a >= 2 GiB floor, so they alone cannot show the flip.
OLD_MIN_ROOM = 2 * GIB
LIVE_NOW_ROOM_GIB = (1.90, 2.00, 2.10, 2.18)
PEAK_6G_PINNED = 3908420239      # 3.64 GiB-ish, non-GiB-aligned: peak is not the mover


def _verdicts(m, cap, peak, room_nows, **kw):
    out = []
    for g in room_nows:
        out.append(m.memory_headroom(cap, peak, cap - int(g * GIB), **kw)[0])
    return out


def test_neg_control_old_criterion_flickers_in_live_band():
    """NEGATIVE control = I-4 itself: old 2 GiB floor straddles the operating point."""
    m = _load()
    cap, peak = 6 * GIB, PEAK_6G_PINNED   # peak pinned -> the flip cannot come from it
    old = _verdicts(m, cap, peak, LIVE_NOW_ROOM_GIB, min_room=OLD_MIN_ROOM)
    assert False in old and True in old, old      # red/green alternation reproduced


def test_neg_control_new_criterion_steady_in_live_band():
    """Identical inputs, new default floor -> every sample green (no flicker)."""
    m = _load()
    cap, peak = 6 * GIB, PEAK_6G_PINNED
    new = _verdicts(m, cap, peak, LIVE_NOW_ROOM_GIB)
    assert all(new), new
    assert m.F2_MIN_ROOM_BYTES == GIB


def test_pos_control_peak_pinned_at_cap_is_red_both_ways():
    """POSITIVE 1: peak == cap (cap glued to high-water mark) -> red, either way."""
    m = _load()
    cap = 6 * GIB
    ok_new, d_new = m.memory_headroom(cap, cap, 5 * GIB)
    ok_old, _old_d = m.memory_headroom(cap, cap, 5 * GIB, min_room=OLD_MIN_ROOM)
    assert ok_new is False and ok_old is False
    assert d_new["room_peak"] == 0 and d_new["ok_peak"] is False
    assert "room_peak" in d_new["verdict_reason"]


def test_pos_control_low_now_room_is_red():
    """POSITIVE 2: room_now = 0.5 GiB -> red via the fallback, cap/peak separated."""
    m = _load()
    cap = 6 * GIB
    ok, d = m.memory_headroom(cap, PEAK_6G_PINNED, cap - GIB // 2)
    assert ok is False, d
    assert d["ok_peak"] is True and d["ok_now"] is False
    assert d["verdict_reason"].startswith("room_now=")


def test_verdict_reason_names_the_failing_criterion():
    """Forensics: a bare ok=False must say WHICH criterion went red."""
    m = _load()
    _ok1, d_p = m.memory_headroom(4 * GIB, 4 * GIB, 3 * GIB)      # primary red only
    _ok2, d_f = m.memory_headroom(6 * GIB, 3908420239, 6 * GIB - GIB // 2)   # fallback red
    assert d_p["verdict_reason"].startswith("room_peak=0<=0"), d_p["verdict_reason"]
    assert d_f["verdict_reason"].startswith("room_now="), d_f["verdict_reason"]
    _ok3, d_b = m.memory_headroom(4 * GIB, 4 * GIB, 4 * GIB)      # both red
    assert "room_peak=0<=0" in d_b["verdict_reason"] and "room_now" in d_b["verdict_reason"]


def test_primary_criterion_is_monotone_in_peak():
    """Monotone = cannot flicker: with current fixed, a red can never go green
    again as peak rises (room_peak = cap - peak only shrinks)."""
    m = _load()
    cap, cur = 6 * GIB, 4 * GIB
    peaks = [int(g * GIB) for g in (3.0, 4.5, 5.5, 5.9, 6.0, 6.5, 8.0)]
    seq = [m.memory_headroom(cap, p, cur)[0] for p in peaks]
    assert False in seq, seq
    first_red = seq.index(False)
    assert all(x is False for x in seq[first_red:]), seq
