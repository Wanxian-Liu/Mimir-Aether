"""N13 段2 批2 · 转移引擎两向 pytest（P-4）—— 负控走真实调用路径 · 零改生产卡。

重跑（cwd = 仓根）:
    bash scripts/pytest_isolated.sh tests/test_n13_state_engine.py -q

纪律（对齐 §D 硬规矩3）：负控用**真实卡 / 真实文件 / 真实不存在的卡**，不用 mock；
「受控差分」= 把真源卡**复制**到 tmp 后只改一个字段，生产卡始终只读。
"""
import argparse
import hashlib
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import state_engine as se  # noqa: E402

REG = se.DEFAULT_REGISTRY
REG_SHA_AT_IMPORT = hashlib.sha256(open(REG, "rb").read()).hexdigest()


# ---------- helpers ----------

def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _copy(tmp_path, name="registry.md"):
    dst = str(tmp_path / name)
    shutil.copyfile(REG, dst)
    return dst


def _set_state(path, card_id, value):
    """受控差分：把副本里某卡的顶格 state 行替换掉（真实文件往返）。"""
    text = open(path, encoding="utf-8").read()
    loc = se.locate_state_line(text, card_id)
    assert loc["line_no"], "card %s not located" % card_id
    lines = text.split("\n")
    lines[loc["line_no"] - 1] = "state: %s" % value
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))


def _drop_line_containing(path, card_id, needle):
    """受控差分：删掉某卡块内第一行含 needle 的行（如 gate:）。"""
    text = open(path, encoding="utf-8").read()
    for _hln, head, body, body_ln in se.split_blocks(text):
        if not se._header_matches(head, card_id):
            continue
        offs = [i for i, ln in enumerate(body.split("\n")) if needle in ln]
        assert offs, "no %r in card %s" % (needle, card_id)
        del_ln = body_ln + offs[0]
        lines = text.split("\n")
        del lines[del_ln - 1]
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(lines))
        return
    raise AssertionError("card not found: %s" % card_id)


def _add_field(path, card_id, text_line):
    """受控差分：在某卡 state 行后插入一行 kv。"""
    ltext = open(path, encoding="utf-8").read()
    loc = se.locate_state_line(ltext, card_id)
    lines = ltext.split("\n")
    lines.insert(loc["line_no"], text_line)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))


def _paths(tmp_path):
    return {"backup_dir": str(tmp_path / "backups"),
            "events_path": str(tmp_path / "events.jsonl"),
            "alerts_path": str(tmp_path / "alerts.jsonl")}


def _apply(card, event, to, path, env, **kw):
    return se.apply_transition(card, event, "mimir", "pytest", True,
                               to_state=to, card_path=path, **dict(env, **kw))


# ---------- J9 寻址（位置闸） ----------

def test_j9_positive_locate_unique_state_in_block():
    text = open(REG, encoding="utf-8").read()
    loc = se.locate_state_line(text, "N3")
    assert loc["rc"] == 0 and loc["hits"] == 1
    assert loc["value"] == "awaiting_decision"
    assert loc["block_head_line"] is not None


def test_j9_negative_arms_real_blocks_and_missing_card():
    text = open(REG, encoding="utf-8").read()
    loc = se.locate_state_line(text, "分支区")
    assert loc["rc"] == 2 and loc["hits"] == 0
    assert se.locate_state_line(text, "N99")["rc"] == 1


def test_j9_negative_whole_file_has_many_states():
    text = open(REG, encoding="utf-8").read()
    loc = se.locate_state_line_whole_file(text)
    assert loc["rc"] == 2 and loc["hits"] == se._count_state_lines(text)


def test_j9_boundary_n1_does_not_hit_n10():
    text = open(REG, encoding="utf-8").read()
    assert se.locate_state_line(text, "N1")["line_no"] == 46


def test_invariant_cards_equal_state_lines():
    text = open(REG, encoding="utf-8").read()
    cards = se.parse_cards(text)
    assert len(cards) == se._count_state_lines(text)
    assert all(c["hits"] == 1 for c in cards)


# ---------- P-1 值白名单 ----------

def test_p1_positive_all_real_states_are_in_whitelist():
    cards = se.parse_cards(open(REG, encoding="utf-8").read())
    assert all(c["state_value_ok"] for c in cards)
    assert se.validate_state_value("awaiting_decision") == "awaiting_decision"


def test_p1_negative_malicious_value_rc_not_zero(tmp_path):
    """Loki 10-10 实证反例的复现路径：locate --card N3 ⇒ 必须 rc!=0。"""
    p = _copy(tmp_path)
    _set_state(p, "N3", "malicious_value")
    loc = se.locate_state_line(open(p, encoding="utf-8").read(), "N3")
    assert loc["rc"] != 0
    assert loc["rc"] == se.RC_INVALID_STATE


def test_p1_negative_invalid_target_refused_before_write(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    before = _sha(p)
    r = _apply("N12", "deps_all_closed", "malicious_value", p, env)
    assert r["rc"] == 6 and r["verdict"] == "refused"
    assert _sha(p) == before          # 拒改 ⇒ 卡字节零变


# ---------- P-2 外域 / 空扫出声 + guard 面 ----------

def test_p2_preflight_positive_real_registry():
    cards = se.parse_cards(open(REG, encoding="utf-8").read())
    assert se.preflight_registry(REG, cards)[0] == 0


def test_p2_preflight_negative_missing_and_foreign(tmp_path):
    missing = str(tmp_path / "nope.md")
    assert se.preflight_registry(missing, [])[0] != 0
    foreign = str(tmp_path / "foreign.md")
    open(foreign, "w", encoding="utf-8").write("# 无卡文件\n")
    assert se.preflight_registry(foreign, [])[0] != 0
    real_foreign = os.path.join(os.path.dirname(REG), "_四方协作协议.md")
    if os.path.exists(real_foreign):
        cards = se.parse_cards(open(real_foreign, encoding="utf-8").read())
        assert se.preflight_registry(real_foreign, cards)[0] != 0


def test_p2_cli_plan_is_loud_on_foreign_registry(tmp_path):
    foreign = str(tmp_path / "foreign.md")
    open(foreign, "w", encoding="utf-8").write("# 无卡文件\n")
    rc = se.cmd_plan(argparse.Namespace(registry=foreign, card=None,
                                        events=str(tmp_path / "e.jsonl")))
    assert rc != 0


def test_p2_plan_gate_open_blocks_would(tmp_path, capsys):
    rc = se.cmd_plan(argparse.Namespace(registry=REG, card=None,
                                        events=str(tmp_path / "e.jsonl")))
    out = capsys.readouterr().out
    assert rc == 0
    assert "reason=gate_open" in out
    assert out.count("WOULD:") == 0


def test_p2_guard_explicit_empty_deps_passes_missing_deps_blocks(tmp_path):
    """受控差分两向：显式 [] ⇒ WOULD；字段缺失 ⇒ fail-closed blocked。"""
    a = _copy(tmp_path, "explicit.md")
    _drop_line_containing(a, "N12", "gate:")
    _add_field(a, "N12", "depends_on: []")
    ca = {c["card_id"]: c for c in
          se.parse_cards(open(a, encoding="utf-8").read())}
    v, line = se.plan_card(ca["N12"], ca, str(tmp_path / "e.jsonl"))
    assert v == "WOULD", line

    b = _copy(tmp_path, "missing.md")
    _drop_line_containing(b, "N12", "gate:")
    cb = {c["card_id"]: c for c in
          se.parse_cards(open(b, encoding="utf-8").read())}
    v2, line2 = se.plan_card(cb["N12"], cb, str(tmp_path / "e.jsonl"))
    assert v2 == "blocked" and "depends_on_missing" in line2, line2


# ---------- P-3 真转移引擎 ----------

def test_p3_dry_run_writes_nothing(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    before = _sha(p)
    r = _apply("N12", "deps_all_closed", "in_progress", p, env, dry_run=True)
    assert r["rc"] == 0 and r["verdict"] == "would_write"
    assert _sha(p) == before
    assert not os.path.exists(env["events_path"])


def test_p3_real_transition_changes_exactly_one_line(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    orig = p + ".orig"
    shutil.copyfile(p, orig)
    r = _apply("N12", "deps_all_closed", "in_progress", p, env)
    assert r["rc"] == 0 and r["verdict"] == "ok"
    assert r["from"] == "pending" and r["to"] == "in_progress"
    assert r["sha_before"] == r["sha_after"]      # 非目标行字节零变
    old = open(orig, encoding="utf-8").read().split("\n")
    new = open(p, encoding="utf-8").read().split("\n")
    changed = [i for i, (x, y) in enumerate(zip(old, new)) if x != y]
    assert len(changed) == 1 and len(old) == len(new)
    assert new[changed[0]].strip() == "state: in_progress"
    # 备份 + manifest + 事件流都在
    assert r["backup"] and os.path.exists(r["backup"])
    assert _sha(r["backup"]) == se.sha256_file(orig)
    assert se.line_count(env["events_path"]) == 1


def test_p3_replay_is_idempotent_no_extra_event(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    assert _apply("N12", "deps_all_closed", "in_progress", p, env)["rc"] == 0
    r2 = _apply("N12", "deps_all_closed", "in_progress", p, env)
    assert r2["rc"] == 0 and r2["verdict"] == "noop"
    assert se.line_count(env["events_path"]) == 1


def test_p3_cas_stale_writer_refused_rc4(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    _set_state(p, "N12", "awaiting_verify")
    before = _sha(p)
    r = se.apply_transition("N12", "L2_failed", "mimir", "pytest", True,
                            to_state="in_progress", card_path=p,
                            expect_from="pending", **env)
    assert r["rc"] == 4 and r["reason"] == "state_mismatch"
    assert _sha(p) == before


def test_p3_frozen_card_denied(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    _set_state(p, "N3", "frozen")
    before = _sha(p)
    r = _apply("N3", "deadline_exceeded", "stalled", p, env)
    assert r["rc"] == 7 and "FROZEN" in r["reason"]
    assert _sha(p) == before
    assert "FROZEN_REJECT" in open(env["alerts_path"], encoding="utf-8").read()


def test_p3_transition_table_denies_illegal_pair(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    before = _sha(p)
    r = _apply("N4", "deps_all_closed", "in_progress", p, env)
    assert r["rc"] == se.RC_TABLE_DENY
    assert _sha(p) == before


def test_p3_drill_ok_then_tampered_fails(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    r = _apply("N12", "deps_all_closed", "in_progress", p, env)
    assert r["rc"] == 0
    d = se.restore_drill(r["backup"], card_id="N12", expect_state="pending",
                         tmp_dir=str(tmp_path / "drill"))
    assert d["rc"] == 0 and d["sha_match"] is True and d["state_match"] is True
    bad = str(tmp_path / "tampered.md")
    shutil.copyfile(r["backup"], bad)
    with open(bad, "a", encoding="utf-8") as fh:
        fh.write("X\n")
    d2 = se.restore_drill(bad, expect_sha=se.sha256_file(r["backup"]),
                          card_id="N12", tmp_dir=str(tmp_path / "drill"))
    assert d2["rc"] != 0 and d2["sha_match"] is False


def test_p3_reconcile_positive_and_split(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    assert _apply("N12", "deps_all_closed", "in_progress", p, env)["rc"] == 0
    ok = se.reconcile_check(p, events_path=env["events_path"],
                            alerts_path=env["alerts_path"])
    assert ok["rc"] == 0 and ok["splits"] == []
    _set_state(p, "N12", "awaiting_verify")          # 受控差分造撕裂
    bad = se.reconcile_check(p, events_path=env["events_path"],
                             alerts_path=env["alerts_path"])
    assert len(bad["splits"]) == 1
    assert bad["lines"][0].startswith("STATE_SPLIT card=N12")
    assert "STATE_SPLIT" in open(env["alerts_path"], encoding="utf-8").read()


def test_p3_guard_not_passed_refuses(tmp_path):
    p = _copy(tmp_path)
    env = _paths(tmp_path)
    before = _sha(p)
    r = se.apply_transition("N12", "deps_all_closed", "mimir", "pytest", False,
                            to_state="in_progress", card_path=p, **env)
    assert r["rc"] == 5 and r["verdict"] == "refused"
    assert _sha(p) == before


def test_no_test_touched_the_production_registry():
    """硬边界：整轮测试跑完，生产卡字节不变。"""
    assert _sha(REG) == REG_SHA_AT_IMPORT
