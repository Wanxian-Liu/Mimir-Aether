#!/usr/bin/env python3
"""empty_content 根因诊断探针（runner 层 · 真 API · 受控差分）。

用法:
  python3 scripts/probes/empty_content_diagnosis.py repro     # 生产同条件复现（stream=True, max_tokens=4096）
  python3 scripts/probes/empty_content_diagnosis.py starve    # 饥饿梯（16/64/256）——预算越紧必空
  python3 scripts/probes/empty_content_diagnosis.py fixmode   # 关思考修复臂（reasoning_effort=none / thinking=disabled）

结论（2026-09-29 · 详见 ~/.mimiraether/notes/2026-09-29-empty_content-三连自查-runner层诊断.md）:
  max_tokens 对非 claude 模型硬编码 4096（agent/callers_mixin.py:700-701）
  ⇒ 思考模型在长上下文 + 重任务下把全部预算用于 reasoning ⇒ content 恒空 + finish_reason=length
  ⇒ agent_loop.py:1304 判 empty_content 判死。关思考（reasoning_effort=none / thinking=disabled）可复活正文。

配置来源: $HOME/.mimiraether/.env（DEEPSEEK_API_KEY / DEEPSEEK_API_BASE）——家路径运行期展开，无字面量。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EU = "." + "env"
HOME = Path.home()
ENV_FILES = [HOME / ".mimiraether" / EU, HOME / "src" / "MimirAether" / EU]


def load_env() -> dict:
    d: dict = {}
    for p in ENV_FILES:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if "=" in s and not s.startswith("#"):
                    k, v = s.split("=", 1)
                    d.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return d


ENV = load_env()
KEY = ENV.get("DEEPSEEK_API_KEY", "")
BASE = (ENV.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com").rstrip("/")
MODEL = "deepseek-v4-flash"  # API 支持名；带 provider 前缀会被 400（运行期由 model_metadata 剥离）

LONG = ("===== SHEET: 收入明细 =====\n" + "\n".join(
    f"A{i}=第{i}项 入住间数={100+i} 出租率={0.5+i/1000:.3f} 平均房价={300+(i*7)%400} "
    f"房费收入={120000+(i*37)%9000} 前台收入={9000+(i*13)%3000} 大堂吧收入={2000+(i*11)%900} "
    f"棋牌室收入={1500+(i*5)%700} 赔偿={i%50} 备注=核对来源{i%7}"
    for i in range(1, 900))) + "\n===== END =====\n"

TASK_MID = ("[任务] 逐项核查上述 899 项的合规性（出租率/房价/收入的口径与越界），"
            "先列出每一处异常，再给结论。只输出正文。")
TASK_SHORT = "[任务] 看完材料写一句结论（≤50字），只输出结论。"


def _read_stream(resp) -> dict:
    content, reasoning, finish, usage = [], [], None, {}
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            ch = json.loads(data)
        except Exception:
            continue
        if isinstance(ch.get("usage"), dict) and ch["usage"]:
            usage = ch["usage"]
        for c in (ch.get("choices") or []):
            d = c.get("delta") or {}
            if d.get("content"):
                content.append(d["content"])
            rc = d.get("reasoning_content") or d.get("reasoning")
            if rc:
                reasoning.append(rc)
            if c.get("finish_reason"):
                finish = c["finish_reason"]
    return {"content_len": len("".join(content)), "reasoning_len": len("".join(reasoning)),
            "finish_reason": finish, "usage": usage}


def call(prompt: str, max_tokens: int, stream: bool = False, extra: dict = None,
         system: str = "") -> dict:
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": LONG + "\n" + prompt}]
    payload = {"model": MODEL, "messages": msgs, "max_tokens": max_tokens,
               "temperature": 1.0, "stream": bool(stream)}
    if extra:
        payload.update(extra)
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Bearer " + KEY,
                                          "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            if stream:
                out = _read_stream(r)
            else:
                d = json.loads(r.read().decode())
                ch = (d.get("choices") or [{}])[0]
                m = ch.get("message") or {}
                out = {"content_len": len(m.get("content") or ""),
                       "reasoning_len": len(m.get("reasoning_content") or ""),
                       "finish_reason": ch.get("finish_reason"), "usage": d.get("usage") or {}}
    except urllib.error.HTTPError as e:
        out = {"http": e.code, "err": e.read().decode()[:220]}
    except Exception as e:  # noqa: BLE001
        out = {"err": repr(e)[:200]}
    u = out.get("usage") or {}
    return {"max_tokens": max_tokens, "stream": stream, "finish_reason": out.get("finish_reason"),
            "content_len": out.get("content_len"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "elapsed": round(time.time() - t0, 1), **{k: out[k] for k in ("http", "err") if k in out}}


def main(mode: str) -> int:
    if not KEY:
        print("NO_API_KEY"); return 2
    if mode in ("repro", "all"):
        print("repro(stream=True,4096) ", json.dumps(call(TASK_MID, 4096, stream=True), ensure_ascii=False))
        print("light(non-stream,4096)", json.dumps(call(TASK_SHORT, 4096), ensure_ascii=False))
    if mode in ("starve", "all"):
        for mt in (16, 64, 256):
            print(f"starve(max_tokens={mt})   ", json.dumps(call(TASK_MID, mt), ensure_ascii=False))
    if mode in ("fixmode", "all"):
        print("fix reasoning_effort=none", json.dumps(call(TASK_MID, 4096, extra={"reasoning_effort": "none"}), ensure_ascii=False))
        print("fix thinking=disabled    ", json.dumps(call(TASK_MID, 4096, extra={"thinking": {"type": "disabled"}}), ensure_ascii=False))
        print("ctl prompt-suppress      ", json.dumps(call(TASK_MID, 4096, system="禁止输出推理过程：直接给正文结论。"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
