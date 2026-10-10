"""N13 段2 批2 · 转移引擎两向 pytest（P-4）—— 负控走真实调用路径 · 零改生产卡。

重跑（cwd = 仓根）:
    bash scripts/pytest_isolated.sh tests/test_n13_state_engine.py -q

纪律（对齐 §D 硬规矩3）：负控用**真实卡 / 真实文件 / 真实不存在的卡**，不用 mock；
「受控差分」= 把真源卡**复制**到 tmp 后只改一个字段，生产卡始终只读。
"""
import argparse
import hashlib
import json
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




# ================= N13 段3 · G1-G4 两向 pytest =================
# 纪律同上：负控走真实文件往返（副本受控差分）；生产卡全程只读。

def _seg3_cfg(tmp_path):
    """自造 config.yaml 真源（不读生产 config · 不与运行时耦合）。"""
    p = str(tmp_path / "config.yaml")
    open(p, "w", encoding="utf-8").write("FEISHU_HOME_CHANNEL: oc_test_home\n")
    return p, "oc_test_home"


def _seg3_fp(cfg, home):
    return se.derive_sender_fingerprint(se.STOP_ORDER_CHANNEL, home, cfg)


def _whole(tmp_path, name, body):
    p = str(tmp_path / name)
    open(p, "w", encoding="utf-8").write(body)
    return open(p, encoding="utf-8").read()


# ---------- G1 值白名单（全路径加严） ----------

def test_g1_positive_whole_file_unique_legal_value(tmp_path):
    text = _whole(tmp_path, "one.md", "### N1 · x\nstate: pending\n")
    r = se.whole_file_guard_result(text)
    assert r["rc"] == 0 and r["value"] == "pending" and r["line_no"] == 2


def test_g1_negative_whole_file_malicious_value_rc6(tmp_path):
    """段2 整文件口径的静默面：唯一命中 + 非法值 ⇒ 必须 rc=6（非 0）。"""
    text = _whole(tmp_path, "bad.md", "### N1 · x\nstate: malicious_value\n")
    r = se.whole_file_guard_result(text)
    assert r["rc"] != 0
    assert r["rc"] == se.RC_INVALID_STATE


def test_g1_negative_whole_file_position_gate_still_rc2(tmp_path):
    """位置闸不得被值闸吞掉：真实 registry 11+ 条 state ⇒ 仍 rc=2。"""
    text = open(REG, encoding="utf-8").read()
    r = se.whole_file_guard_result(text)
    assert r["rc"] == 2


def test_g1_parity_block_and_whole_file_same_rc(tmp_path):
    """两口径同值 ⇒ 同 rc（块内 / 整文件不再分叉）。"""
    text = _whole(tmp_path, "bad2.md", "### N1 · x\nstate: malicious_value\n")
    blob = se.locate_state_line(text, "N1")
    whole = se.whole_file_guard_result(text)
    assert blob["rc"] == whole["rc"] == se.RC_INVALID_STATE


def test_g1_positive_real_registry_blocks_all_legal():
    cards = se.parse_cards(open(REG, encoding="utf-8").read())
    assert cards and all(c["state_value_ok"] for c in cards)


# ---------- G2 外域 / 格式错出声 ----------

def test_g2_negative_path_no_cards_no_state_all_loud(tmp_path):
    missing = str(tmp_path / "nope.md")
    rc1, m1 = se.preflight_registry(missing, [])
    assert rc1 != 0 and m1.startswith("ERROR")

    t = _whole(tmp_path, "nocards.md", "# 无卡\n正文\n")
    rc2, m2 = se.preflight_registry(str(tmp_path / "nocards.md"),
                                    se.parse_cards(t))
    assert rc2 != 0 and m2.startswith("ERROR")

    t = _whole(tmp_path, "nostate.md", "### N1 · x\nowner: mimir\n")
    rc3, m3 = se.preflight_registry(str(tmp_path / "nostate.md"),
                                    se.parse_cards(t))
    assert rc3 != 0 and m3.startswith("ERROR")


def test_g2_negative_sub_block_state_count_drift(tmp_path):
    """段2 静默面：块内 state!=1 但**全局计数相等** ⇒ 旧闸放行，新闸必须出声。"""
    body = "### N1 · a\nstate: pending\nstate: pending\n### N2 · b\nowner: x\n"
    p = str(tmp_path / "drift.md")
    open(p, "w", encoding="utf-8").write(body)
    cards = se.parse_cards(body)
    rc, msg = se.preflight_registry(p, cards)
    assert rc != 0 and msg.startswith("ERROR") and "!=1" in msg
    assert se._count_state_lines(body) == len(cards)      # 全局相等（旧闸看不到）


def test_g2_positive_real_registry():
    cards = se.parse_cards(open(REG, encoding="utf-8").read())
    assert se.preflight_registry(REG, cards)[0] == 0


# ---------- G3 停止令渠道指纹（白名单）· T11/T12 ----------

def test_g3_positive_liuge_feishu_dm_accepted(tmp_path):
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    v = se.verify_stop_order({"channel": se.STOP_ORDER_CHANNEL, "chat_id": home,
                              "sender_fingerprint": fp, "scope": "all",
                              "action": "stop", "order_id": "T-1"}, cfg)
    assert v["ok"] and v["decision"] == "accepted"
    assert v["fingerprint"] == "feishu:dm:oc_test_home"


def test_g3_negative_channel_not_whitelisted(tmp_path):
    """预置卡 L777 负控的收编：非白名单渠道（讨论卡/群/信箱）⇒ 拦住。"""
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    for ch in ("discussion", "buzz-inbox", "feishu:group", "feishu:dm "):
        v = se.verify_stop_order({"channel": ch, "chat_id": home,
                                  "sender_fingerprint": fp, "scope": "all",
                                  "order_id": "T-%s" % ch}, cfg)
        assert not v["ok"], ch
        assert "not in whitelist" in v["reason"]


def test_g3_negative_chat_id_must_exact_match(tmp_path):
    """精确匹配（非前缀）：home 加尾字符也必须拒。"""
    cfg, home = _seg3_cfg(tmp_path)
    for bad_cid in ("oc_attacker", home + "x", home[:-1], home.upper()):
        v = se.verify_stop_order({"channel": se.STOP_ORDER_CHANNEL,
                                  "chat_id": bad_cid,
                                  "sender_fingerprint": "feishu:dm:" + bad_cid,
                                  "scope": "all", "order_id": "T-x"}, cfg)
        assert not v["ok"], bad_cid


def test_g3_negative_missing_and_forged_fingerprint(tmp_path):
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    miss = se.verify_stop_order({"channel": se.STOP_ORDER_CHANNEL,
                                 "chat_id": home, "scope": "all",
                                 "order_id": "T-m"}, cfg)
    assert not miss["ok"] and "missing" in miss["reason"]
    forged = se.verify_stop_order({"channel": se.STOP_ORDER_CHANNEL,
                                   "chat_id": home,
                                   "sender_fingerprint": fp + ":forged",
                                   "scope": "all", "order_id": "T-f"}, cfg)
    assert not forged["ok"] and "mismatch" in forged["reason"]


def test_g3_negative_fail_closed_when_config_unreadable(tmp_path):
    """渠道白名单真源读不到 ⇒ fail-closed（拒一切停止令）。"""
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    gone = str(tmp_path / "absent.yaml")
    v = se.verify_stop_order({"channel": se.STOP_ORDER_CHANNEL, "chat_id": home,
                              "sender_fingerprint": fp, "scope": "all",
                              "order_id": "T-c"}, gone)
    assert not v["ok"]
    assert se.derive_sender_fingerprint(se.STOP_ORDER_CHANNEL, home, gone) is None


def test_g3_negative_scope_and_action_denied(tmp_path):
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    base = {"channel": se.STOP_ORDER_CHANNEL, "chat_id": home,
            "sender_fingerprint": fp}
    assert not se.verify_stop_order(dict(base, scope="bogus",
                                         order_id="T-s"), cfg)["ok"]
    assert not se.verify_stop_order(dict(base, scope="all", action="nuke",
                                         order_id="T-a"), cfg)["ok"]


# ---------- G4 可撤 + 留痕 ----------

def test_g4_append_then_revoke_is_append_only(tmp_path):
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    log = str(tmp_path / "stop-orders.jsonl")
    order = {"order_id": "T-9", "channel": se.STOP_ORDER_CHANNEL,
             "chat_id": home, "sender_fingerprint": fp, "scope": "all",
             "action": "stop"}
    v = se.verify_stop_order(order, cfg)
    se.append_stop_event(se.stop_order_event(order, v, card_id="N12"), log)
    first_raw = open(log, encoding="utf-8").readline()
    rec = json.loads(first_raw)
    assert rec["sender_fingerprint"] == fp and rec["decision"] == "accepted"
    assert rec["reason"] == "ok" and rec["card_id"] == "N12"

    se.revoke_stop_order("T-9", path=log)
    lines = open(log, encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 2
    last = json.loads(lines[-1])
    assert last["decision"] == "revoked" and last["revokes"] == "T-9"
    assert open(log, encoding="utf-8").readline() == first_raw   # 历史行零改
    assert se.stop_order_seen("T-9", log) and not se.stop_order_seen("X", log)


def test_g4_negative_revoke_unknown_order_rc1(tmp_path, capsys):
    log = str(tmp_path / "stop-orders.jsonl")
    rc = se.cmd_unstop(argparse.Namespace(order_id="NOPE", stop_log=log,
                                          actor="pytest"))
    assert rc == 1
    assert "not found" in capsys.readouterr().out
    assert not os.path.exists(log)


def test_g4_cli_accepted_rc0_refused_rc8_duplicate_no_extra_line(tmp_path,
                                                                 capsys):
    cfg, home = _seg3_cfg(tmp_path)
    fp = _seg3_fp(cfg, home)
    log = str(tmp_path / "stop-orders.jsonl")
    good = argparse.Namespace(order_id="C-1", channel=se.STOP_ORDER_CHANNEL,
                              chat_id=home, sender_fingerprint=fp,
                              scope="all", action="stop", card="N12",
                              config=cfg, stop_log=log, record=True)
    assert se.cmd_stop(good) == 0
    assert se.line_count(log) == 1
    assert se.cmd_stop(good) == 0          # 重放：幂等，不重复落行
    assert se.line_count(log) == 1
    capsys.readouterr()

    bad = argparse.Namespace(order_id="C-2", channel="discussion",
                             chat_id=home, sender_fingerprint=fp,
                             scope="all", action="stop", card="N12",
                             config=cfg, stop_log=log, record=True)
    assert se.cmd_stop(bad) == se.RC_STOP_REFUSED
    out = capsys.readouterr().out
    assert "ERROR: stop order refused" in out       # 出声（不静默）
    assert se.line_count(log) == 2                  # 拒绝也留痕


def test_no_test_touched_the_production_registry():
    """硬边界：整轮测试跑完，生产卡字节不变。"""
    assert _sha(REG) == REG_SHA_AT_IMPORT
