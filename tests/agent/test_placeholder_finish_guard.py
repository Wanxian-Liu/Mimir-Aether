"""#3 · F4（2026-10-07 落盘）：「待补」类占位检测判据。

## 缺口原文（10-05 自认）
「F4 认窄化：生产端已接 `evaluate_finish`，缺『待补』占位检测判据」。
即：判定与记账通道都在，但**没有**判「交付物正文还留着占位符却宣称完成」的规则。

## 判据形态（AGENTS §8.5：纯函数 + 读数，非文字承诺）
  正控：正文含「待补」且未显式标未闭 ⇒ 拦（不得判为完成）
  负控：同文只把占位词换掉（唯一变量）⇒ 不再以本理由拦
  显式未闭：正文自称「半段 / 未闭 / 待复核」⇒ 放行（占位是被声明的）
  回滚：MIMIR_PLACEHOLDER_GUARD=0 ⇒ 本判据失效
"""
import json

from agent import verify_before_report_guard as g


def _msgs(text=""):
    return [
        {"role": "user", "content": "把第2单做完并给回执"},
        {"role": "assistant", "content": text,
         "tool_calls": [{"id": "c", "type": "function",
                         "function": {"name": "read_file",
                                      "arguments": json.dumps({"path": "/repo/x.py"})}}]},
        {"role": "tool", "tool_call_id": "c", "content": "ok"},
    ]


# 注意：本正文**不得**命中 RS17 探针自证闸（否定类声明）——否则 block_reason
# 会先被 probe_attest 占据，本用例就测不到 F4 判据了（受控差分 = 唯一变量）。
# 措辞注意：不得出现「已完成」等 assertive claim（会先被 RS17 探针自证闸拦下，
# block_reason 被 probe_attest 占据 ⇒ 测不到 F4 判据）。实测 D 版正文 probe_attest=None。
BODY_PLACEHOLDER = (
    "## 交付\n空跑闸门修复：受控差分通过（旧版静默 4 轮 / 新版 0 轮）；\n"
    "- 待补：台账回填\n- 待补：用例入库\n- 待补：边界声明\n"
)
BODY_NORMAL = BODY_PLACEHOLDER.replace("待补", "已补")


# ── 正控 ──────────────────────────────────────────────────────────────
def test_positive_placeholder_is_unclosed():
    assert g.has_unclosed_placeholder(BODY_PLACEHOLDER) is True


def test_positive_guard_blocks_with_reason():
    assert g.should_block_finish(_msgs(BODY_PLACEHOLDER), BODY_PLACEHOLDER) is True
    assert g.get_last_block_reason() == "placeholder_unclosed"


# ── 负控（唯一变量 = 占位词）──────────────────────────────────────────
def test_negative_same_body_without_placeholder_not_blocked_by_this_rule():
    assert g.has_unclosed_placeholder(BODY_NORMAL) is False
    g.should_block_finish(_msgs(BODY_NORMAL), BODY_NORMAL)
    assert g.get_last_block_reason() != "placeholder_unclosed"


def test_negative_normal_delivery_body():
    body = ("## 交付\n已完成空跑闸门修复。重跑命令: python3 scripts/probes/x.py\n"
            "复算数字: 旧版静默 4 轮 / 新版 0 轮。边界：未动 chroma / gateway / cron。\n")
    assert g.has_unclosed_placeholder(body) is False


# ── 显式未闭 ⇒ 放行（占位是被声明的）────────────────────────────────
def test_explicit_unclosed_marker_passes():
    body = BODY_PLACEHOLDER + "\n（本段为半段·未闭·待复核）\n"
    assert g.has_unclosed_placeholder(body) is False


def test_explicit_wip_marker_passes():
    body = "## 进行中\nTODO：还有两件没做，本轮交棒。\n" + "x" * 60
    assert g.has_unclosed_placeholder(body) is False


# ── 边界 ─────────────────────────────────────────────────────────────
def test_short_text_not_judged():
    assert g.has_unclosed_placeholder("待补") is False
    assert g.has_unclosed_placeholder("") is False
    assert g.has_unclosed_placeholder(None) is False


def test_env_rollback(monkeypatch):
    monkeypatch.setenv("MIMIR_PLACEHOLDER_GUARD", "0")
    g.should_block_finish(_msgs(BODY_PLACEHOLDER), BODY_PLACEHOLDER)
    assert g.get_last_block_reason() != "placeholder_unclosed"


def test_env_default_on(monkeypatch):
    monkeypatch.delenv("MIMIR_PLACEHOLDER_GUARD", raising=False)
    assert g.placeholder_guard_enabled() is True


# ── 记账口径（量具可读）──────────────────────────────────────────────
def test_failure_type_maps_to_same_name():
    assert g._failure_type_for(_msgs(BODY_PLACEHOLDER), BODY_PLACEHOLDER,
                               "placeholder_unclosed") == "placeholder_unclosed"


def test_turn_has_claim_true_for_placeholder_reason():
    assert g._turn_has_claim(BODY_PLACEHOLDER, "placeholder_unclosed") is True
