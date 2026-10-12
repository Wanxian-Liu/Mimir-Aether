#!/usr/bin/env python3
"""N8 成功侧自证（R1 读回法）· 只读 · 零新消息 · 零新群

用途
----
cron「N8 投递可听性双控」的**成功侧**检查：证明「投递成功」可以被**读回**验证。

为什么需要它（本文件存在的理由）
--------------------------------
原 N8 双控只有**失败侧**可见（正控臂 = 不存在的 chat_id ⇒ 日志报 FAILED）。
「成功侧可见」此前被判为「需建**专用测试群**（= 外操）」，故长期挂账未闭。
2026-10-12 实测**推翻**该前提：`LIST_CHAT_MESSAGES` 可零成本读回本 app 在
已知 chat 中已发出的消息（`http=200 code=0 items=5`）。
⇒ 无需建群、无需发新消息、无需骚扰任何人（owner 2026-10-12 批准）。

三个控制组（AGENTS §9 档位④：两向 + 真实样本）
-----------------------------------------------
正控 = 真 chat 列举            ⇒ 期望 code=0 且 items>0
负控 = 不存在的 chat_id        ⇒ 期望 code!=0（证明「长相相似的靶」能区分）
真实 = 本 run 实际使用的 chat  ⇒ 与正控同源，仅用于记录读数

输出契约（AGENTS §8.4：可复现）
-------------------------------
stdout 末行 `VERDICT=PASS|FAIL|BLOCKED`；rc 0=通 / 1=拦 / 2=环境缺件。

陷阱（本轮真实踩过 · 别重犯）
-----------------------------
`gateway.log` 里 `[Feishu] send success message_id=… chat_id=oc_8af3ea…` 的
**message_id / chat_id 被适配器截断**（`feishu_adapter.py:1385-1388`，
`str(mid)[:24]`），且 message_id 的截断**不带省略号**（静默）⇒ 拿日志 id
直接读回必报 `99992354 not a valid open_message_id`，看着像「消息不存在」，
实为**日志截断**。⇒ 本脚本**不**用日志 id，只用**列举返回**的 id。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ORIGIN = "https://open.feishu.cn"
MIMIR = Path(os.environ.get("MIMIR_HOME") or (Path.home() / ".mimiraether"))
ENV_FILE = MIMIR / ".env"
LOG_FILE = MIMIR / "logs" / "gateway.log"
OC_ANY = re.compile(r"(oc_[0-9a-f]{20,})")


def load_env() -> dict:
    """读 MIMIR_HOME/.env（不依赖 /proc 注入 —— cron 子进程无 gateway 内存）。"""
    out = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_chat_id(log_text: str) -> tuple:
    """定位真实 chat_id（只读日志，不猜）。

    优先 `chat=` 标记行（`inbound message: … chat=oc_…`，**不截断**），
    回退到全文件出现最频的非全零 oc_。返回 (chat_id, 依据说明)。
    """
    marked = re.findall(r"chat=(oc_[0-9a-f]{20,})", log_text)
    marked = [c for c in marked if not re.fullmatch(r"oc_0+", c)]
    if marked:
        counts = {}
        for c in marked:
            counts[c] = counts.get(c, 0) + 1
        best = max(counts.items(), key=lambda kv: kv[1])
        return best[0], f"chat= 标记 ×{best[1]}"
    loose = [c for c in OC_ANY.findall(log_text) if not re.fullmatch(r"oc_0+", c)]
    if not loose:
        return None, "no-chat-found"
    counts = {}
    for c in loose:
        counts[c] = counts.get(c, 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0], f"loose-oc_ 最频 ×{best[1]}"


def get_token(env: dict):
    aid = env.get("FEISHU_APP_ID", "")
    sec = env.get("FEISHU_APP_SECRET", "")
    if not aid or not sec:
        return None, "missing FEISHU_APP_ID/SECRET in .env"
    payload = json.dumps({"app_id": aid, "app_secret": sec}).encode()
    req = urllib.request.Request(
        f"{ORIGIN}/open-apis/auth/v3/tenant_access_token/internal",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read())
    except Exception as ex:  # noqa: BLE001
        return None, f"token-request-failed: {type(ex).__name__}"
    tok = j.get("tenant_access_token")
    return (tok, "ok") if tok else (None, f"token-denied: code={j.get('code')}")


def call(url: str, tok: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as ex:
        try:
            return ex.code, json.loads(ex.read().decode(errors="replace"))
        except Exception:  # noqa: BLE001
            return ex.code, {}
    except Exception as ex:  # noqa: BLE001
        return -1, {"err": f"{type(ex).__name__}:{ex}"}


def brief(st, j) -> str:
    data = j.get("data") if isinstance(j.get("data"), dict) else {}
    items = data.get("items") or []
    return (f"http={st} code={j.get('code')} items={len(items)} "
            f"msg={str(j.get('msg'))[:60]!r}")


def list_msgs(chat: str, tok: str):
    q = urllib.parse.urlencode({
        "container_id_type": "chat", "container_id": chat,
        "sort_type": "ByCreateTimeDesc", "page_size": 5})
    return call(f"{ORIGIN}/open-apis/im/v1/messages?{q}", tok)


FAKE_CHAT = "oc_" + "f" * 32  # 负控靶：形似真 id、必然不存在


def main() -> int:
    print("N8 成功侧自证（R1 读回法 · 只读 · 零新消息 · 零新群）")
    env = load_env()
    tok, note = get_token(env)
    print(f"TOKEN={note}")
    if not tok:
        print("VERDICT=BLOCKED")
        return 2

    log_text = LOG_FILE.read_text(errors="replace") if LOG_FILE.exists() else ""
    chat, how = resolve_chat_id(log_text)
    if "--chat-id" in sys.argv:
        chat, how = sys.argv[sys.argv.index("--chat-id") + 1], "cli-override"
    print(f"CHAT_SOURCE={how}")
    print(f"CHAT_ID={chat}")
    if not chat:
        print("VERDICT=BLOCKED")
        return 2

    st_pos, j_pos = list_msgs(chat, tok)
    print(f"POS(真chat列举): {brief(st_pos, j_pos)}")
    ids = [it.get("message_id") for it in
           ((j_pos.get("data") or {}).get("items") or [])]
    print(f"POS_IDS={ids[:3]}")

    st_neg, j_neg = list_msgs(FAKE_CHAT, tok)
    print(f"NEG(假chat列举): {brief(st_neg, j_neg)}")

    pos_ok = st_pos == 200 and j_pos.get("code") == 0 and bool(ids)
    neg_ok = not (st_neg == 200 and j_neg.get("code") == 0)
    if pos_ok and neg_ok:
        print("VERDICT=PASS")
        print("重跑命令: ~/src/MimirAether/scripts/check_feishu_delivery_visibility.py")
        print(f"复算数字: POS items={len(ids)} 且 NEG code={j_neg.get('code')} (正控 code=0 / 负控 code!=0)")
        return 0
    print(f"VERDICT=FAIL pos_ok={pos_ok} neg_ok={neg_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
