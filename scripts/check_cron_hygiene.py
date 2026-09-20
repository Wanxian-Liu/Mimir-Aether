#!/usr/bin/env python3
"""Cron 记账卫生闸（B1/B3 · 2026-09-19 刘哥批 · 行175 三项补强 2026-09-21）。

为什么（根因，不是洁癖）：
    ~/.mimiraether/cron/jobs.json 长期存在三种「写而不跑 · 判据存在但没人读」的形态：
      ① enabled=false 而**没有任何理由字段** ⇒ 下一轮接手的人（含我）无法判断
         「这是刻意停的，还是坏了漏停的」——本轮自查实测 20/21 属此类。
      ② enabled=true 而 deliver 以 local 起 ⇒ 「跑起来了但没人收得到」，
         静默失败不可听（N8/N9/N10 同族病根）。
      ③ enabled=true 而 next_run_at 冻结在过去 ⇒ 调度器不会真跑它。
    三者都不是「能不能跑」的问题，而是**判据在盘上但没人读**。本闸把这三条变成机器
    判据，接进 Tier-0 Gate1（守卫式 if ! ...; then exit 1; fi，防 set +e 吞码）。

行175 三项补强（Hermes 派单 · Loki 3 项高优 · 本机实测后定级）：
    ① R4 理由**实质化**：原来只判「有没有理由」，「恢复」两字即可过关（记账是假的）。
       现加 MIN_REASON_CHARS=10 + 四要素（谁/何时/为何/可逆转）必填。
       **分级**（不改 jobs.json 前提下的迁移窗口）：停用时刻能证明早于
       REASON_STANDARD_CUTOFF ⇒ 记 LEGACY（历史债 · 可见但不算 FAIL）；新停用/无法证明 ⇒ FAIL。
       本机实测：11 件历史薄理由全可证明早于 cutoff ⇒ 不假红。
    ② R5 飞书通道**可达性**：闸以前只看盘上字段，通道断了照样全绿（「启用即静默」的镜像）。
       加真实 ping（tenant_access_token 端点）：AUTH_ERR/NO_CREDENTIALS ⇒ FAIL（确定性），
       TRANSPORT_ERR ⇒ WARN（可能瞬断）。**限流保护**：TTL 缓存（默认 1800s；按 origin +
       凭据指纹分桶）内复用上次结论，不重复打 API；MIMIR_CRON_HYGIENE_NET=0 全关。
    ③ R3 僵尸时间 WARN→FAIL：next_run_at 冻结在过去 = 调度器根本不跑它，属真病灶。

规则（只读状态；本脚本**从不写** jobs.json）：
    R1 FAIL        enabled=false 且 disable_reason/paused_reason 皆空
    R2 FAIL        enabled=true 且 deliver 以 local 起（豁免：local_deliver_reason 非空）
    R3 FAIL        enabled=true 且 next_run_at 早于 now（僵尸/冻结）
    R4 FAIL/LEGACY enabled=false 且理由非实质（len < 10 或缺四要素）
    R5 FAIL/WARN   enabled=true 且投递目标为 feishu/lark 时，通道可达性 ping 不通过

级别：FAIL（**改退出码**）· WARN（不改退出码）· LEGACY（历史债 · 可见 · 不改退出码）
退出码：0 = 无 FAIL（WARN/LEGACY 允许，照打）；1 = 至少一条 FAIL；jobs 文件不存在 = SKIP(0)
（CI 上没有 ~/.mimiraether ⇒ 必须 SKIP 而非红；SKIP 早于任何网络动作 ⇒ CI 不联网。）

负控（见 --selftest 与 tests/scripts/test_check_cron_hygiene.py）：
    FAIL 病例（R1/R2/R3）+ R4 两形态（新停用薄理由 FAIL · 历史薄理由 LEGACY）
    + R5 两形态（AUTH_ERR FAIL · TRANSPORT_ERR WARN），加**孪生合规对照**断言 PASS ——
    只证明「坏样本被拒」不算数，必须同时证明「好样本不被误拦」（含历史薄理由不假红对照）。

用法：
    python3 scripts/check_cron_hygiene.py                 # 查真实 jobs.json（含 R5 真 ping，TTL 内复用）
    python3 scripts/check_cron_hygiene.py --selftest      # 合成病例自证（不联网）
    python3 scripts/check_cron_hygiene.py --jobs-file P   # 指定文件（测试用）
    python3 scripts/check_cron_hygiene.py --no-net        # 本次关闭 R5 网络动作
环境变量（全部可选）：
    MIMIR_CRON_HYGIENE_NET=0            关闭 R5 网络动作（打印 SKIP，不静默）
    MIMIR_CRON_HYGIENE_NET_TTL=1800     R5 结论缓存有效期（秒）
    MIMIR_CRON_HYGIENE_FEISHU_STATE     缓存落点（默认 <mimir_home>/data/ops/cron_hygiene_feishu.json）
    MIMIR_CRON_HYGIENE_REASON_CUTOFF    R4 迁移窗口分界（ISO8601，默认 2026-09-20T16:00:00+00:00）
    FEISHU_ORIGIN                       通道 origin 覆盖（默认 https://open.feishu.cn）
    FEISHU_APP_ID / FEISHU_APP_SECRET   凭据（缺则回落 dotenv 面 .mimiraether/.env）

⚠️ 口径自曝（别把它当强判据）：R4 的「四要素」是**子串存在性**检查，不是语义检查 ——
   写满四个词但内容空洞的理由仍会过关。它是**结构性**闸（防「两字敷衍」），非质量裁判。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

EXIT_OK = 0
EXIT_FAIL = 1

RULE_DISABLED_NO_REASON = "R1"
RULE_ENABLED_LOCAL = "R2"
RULE_ENABLED_FROZEN = "R3"
RULE_DISABLED_REASON_THIN = "R4"
RULE_FEISHU_UNREACHABLE = "R5"

LEVEL_FAIL = "FAIL"
LEVEL_WARN = "WARN"
LEVEL_LEGACY = "LEGACY"

MIN_REASON_CHARS = 10
REQUIRED_REASON_FIELDS = ("谁", "何时", "为何", "可逆转")

# 行175 补强生效时刻（= 2026-09-21 00:00 CST）：早于它停用且理由薄的记 LEGACY（迁移窗口）
REASON_STANDARD_CUTOFF = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)

FEISHU_DELIVER_PREFIXES = ("feishu", "lark")
DEFAULT_FEISHU_ORIGIN = "https://open.feishu.cn"
DEFAULT_NET_TTL_S = 1800
PING_TIMEOUT_S = 5

# R5 结论 → 级别；None = 不产 finding。未知结论保守落 WARN（不静默、也不假红）
_VERDICT_LEVELS: Dict[str, Optional[str]] = {
    "AUTH_OK": None,
    "SKIPPED": None,
    "AUTH_ERR": LEVEL_FAIL,
    "AUTH_ERR_HTTP": LEVEL_FAIL,
    "NO_CREDENTIALS": LEVEL_FAIL,
    "TRANSPORT_ERR": LEVEL_WARN,
}


class ReasonAssessment(NamedTuple):
    """停用理由的机器可读评估（全部为盘上读数，非推断）。"""

    text: str
    source: str  # disable_reason / paused_reason / ""
    length: int
    missing: Tuple[str, ...]
    substantive: bool
    stop_ts: Optional[datetime]
    stop_source: str  # paused_at / last_run_at / ""
    legacy: bool


def default_jobs_file() -> Path:
    home = os.environ.get("MIMIR_HOME")
    if not home:
        try:  # 与运行时同一真源；import 失败退回约定路径
            from mimir_constants import get_mimir_home  # type: ignore

            home = str(get_mimir_home())
        except Exception:
            home = str(Path.home() / ".mimiraether")
    return Path(home) / "cron" / "jobs.json"


def _mimir_home() -> Path:
    return default_jobs_file().parent.parent


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):  # 3.10 的 fromisoformat 不认 Z
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _reason_of(job: Dict[str, Any]) -> str:
    """停用理由：disable_reason 或 paused_reason 任一非空即算记账。"""
    for key in ("disable_reason", "paused_reason"):
        val = job.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _reason_source(job: Dict[str, Any]) -> str:
    for key in ("disable_reason", "paused_reason"):
        val = job.get(key)
        if isinstance(val, str) and val.strip():
            return key
    return ""


def _stop_ts(job: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
    """停用时刻（机器可读溯源字段）：paused_at 优先，其次 last_run_at。"""
    for key in ("paused_at", "last_run_at"):
        dt = _parse_ts(job.get(key))
        if dt is not None:
            return dt, key
    return None, ""


def reason_cutoff() -> datetime:
    raw = os.environ.get("MIMIR_CRON_HYGIENE_REASON_CUTOFF")
    parsed = _parse_ts(raw) if raw else None
    return parsed or REASON_STANDARD_CUTOFF


def assess_reason(job: Dict[str, Any], cutoff: Optional[datetime] = None) -> ReasonAssessment:
    """理由实质化评估（行175 补强①）。cutoff 之前的停用记 LEGACY（迁移窗口）。"""
    cutoff = cutoff or reason_cutoff()
    text = _reason_of(job)
    missing = tuple(f for f in REQUIRED_REASON_FIELDS if f not in text)
    substantive = len(text) >= MIN_REASON_CHARS and not missing
    stop_ts, stop_source = _stop_ts(job)
    legacy = bool(text) and stop_ts is not None and stop_ts < cutoff
    return ReasonAssessment(
        text=text,
        source=_reason_source(job),
        length=len(text),
        missing=missing,
        substantive=substantive,
        stop_ts=stop_ts,
        stop_source=stop_source,
        legacy=legacy,
    )

# ---------------------------------------------------------------------------
# R5 · 飞书通道可达性（真实 ping + TTL 缓存）：行175 补强②
# ---------------------------------------------------------------------------


def _feishu_state_path() -> Path:
    override = os.environ.get("MIMIR_CRON_HYGIENE_FEISHU_STATE")
    if override:
        return Path(override)
    return _mimir_home() / "data" / "ops" / "cron_hygiene_feishu.json"


def _dotenv_get(path: Path, key: str) -> str:
    """无依赖读 KEY=VALUE（剥引号 / 行内注释）。只返回值，调用方负责不打印它。"""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            return value[1:-1]
        if " #" in value:
            value = value.split(" #", 1)[0].strip()
        return value
    return ""


def _credentials() -> Tuple[str, str]:
    """凭据面：env 优先，缺则回落 dotenv 文件；只返回，不打印。"""
    app_id = os.environ.get("FEISHU_APP_ID") or ""
    app_secret = os.environ.get("FEISHU_APP_SECRET") or ""
    if app_id and app_secret:
        return app_id, app_secret
    for cand in (_mimir_home() / ".env", Path.home() / ".env"):
        if not cand.exists():
            continue
        app_id = app_id or _dotenv_get(cand, "FEISHU_APP_ID")
        app_secret = app_secret or _dotenv_get(cand, "FEISHU_APP_SECRET")
    return app_id or "", app_secret or ""


def _fp(value: str) -> str:
    """凭据指纹（sha256 前 8 位）—— 用于缓存分桶；绝不落明文。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8] if value else ""


def _read_cache(
    path: Path, origin: str, id_fp: str, ttl_s: int
) -> Optional[Dict[str, Any]]:
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict):
        return None
    if cached.get("origin") != origin or cached.get("id_fp") != id_fp:
        return None  # 异桶（换 origin / 换凭据）⇒ 不命中，避免污染真实结论
    ts = cached.get("ts")
    if not isinstance(ts, (int, float)):
        return None
    age = time.time() - ts
    if age < 0 or age > ttl_s:
        return None
    cached["age_s"] = round(age, 1)
    return cached


def _write_cache(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:  # 缓存写失败不得反噬主判据（只发声）
        print(f"[cron-hygiene] R5 cache-write-failed: {exc}")


def ping_feishu(origin: str, app_id: str, app_secret: str) -> Dict[str, Any]:
    """真打一次 tenant_access_token 端点。只回结论与状态码，绝不回凭据。"""
    url = f"{origin}/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=PING_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
            ok = payload.get("code") == 0 and bool(payload.get("tenant_access_token"))
            return {
                "verdict": "AUTH_OK" if ok else "AUTH_ERR",
                "http": resp.status,
                "code": payload.get("code"),
                "elapsed_s": round(time.time() - t0, 2),
            }
    except urllib.error.HTTPError as exc:
        return {
            "verdict": "AUTH_ERR_HTTP",
            "http": exc.code,
            "elapsed_s": round(time.time() - t0, 2),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "verdict": "TRANSPORT_ERR",
            "error": f"{type(exc).__name__}: {exc}"[:160],
            "elapsed_s": round(time.time() - t0, 2),
        }


def feishu_probe() -> Dict[str, Any]:
    """默认 R5 探针：TTL 内复用缓存（不重复打 API），过期才真 ping。"""
    raw_ttl = os.environ.get("MIMIR_CRON_HYGIENE_NET_TTL") or str(DEFAULT_NET_TTL_S)
    try:
        ttl_s = int(float(raw_ttl))
    except (TypeError, ValueError):
        ttl_s = DEFAULT_NET_TTL_S
    if os.environ.get("MIMIR_CRON_HYGIENE_NET") == "0":
        print("[cron-hygiene] R5 SKIP: net=0（通道可达性未测 ⇒ 不视为通过）")
        return {"verdict": "SKIPPED", "source": "env-off"}
    origin = os.environ.get("FEISHU_ORIGIN") or DEFAULT_FEISHU_ORIGIN
    app_id, app_secret = _credentials()
    id_fp = _fp(app_id)
    state = _feishu_state_path()
    cached = _read_cache(state, origin, id_fp, ttl_s)
    if cached is not None:
        cached["source"] = "cache"
        return cached
    if not (app_id and app_secret):
        result: Dict[str, Any] = {"verdict": "NO_CREDENTIALS", "elapsed_s": 0.0}
    else:
        result = ping_feishu(origin, app_id, app_secret)
    result["source"] = "live"
    payload = dict(result)
    payload.update(
        {"ts": time.time(), "origin": origin, "id_fp": id_fp, "ttl_s": ttl_s}
    )
    _write_cache(state, payload)
    return payload

def _level_for_verdict(verdict: str) -> Optional[str]:
    """R5 结论 → 级别。未知结论落 WARN（发声，但不因「未知」而假红）。"""
    return _VERDICT_LEVELS.get(str(verdict), LEVEL_WARN)


def _is_feishu_deliver(value: Any) -> bool:
    return str(value or "").strip().lower().startswith(FEISHU_DELIVER_PREFIXES)


def evaluate(
    jobs: List[Dict[str, Any]],
    now: Optional[datetime] = None,
    feishu_probe_fn: Optional[Callable[[], Dict[str, Any]]] = None,
) -> List[Tuple[str, str, str]]:
    """返回 [(rule, level, message)]，level 属于 {FAIL, WARN, LEGACY}。"""
    now = now or datetime.now(timezone.utc)
    cutoff = reason_cutoff()
    findings: List[Tuple[str, str, str]] = []
    feishu_dependents: List[str] = []
    for idx, job in enumerate(jobs):
        name = str(job.get("name") or job.get("id") or f"#{idx}")
        jid = str(job.get("id") or "")[:12]
        tag = f"{name} [{jid}]"
        if not job.get("enabled"):
            assessment = assess_reason(job, cutoff)
            if not assessment.text:
                findings.append(
                    (
                        RULE_DISABLED_NO_REASON,
                        LEVEL_FAIL,
                        f"{tag}: 已停用但无理由（disable_reason/paused_reason 皆空）",
                    )
                )
                continue
            if not assessment.substantive:
                why: List[str] = []
                if assessment.length < MIN_REASON_CHARS:
                    why.append(f"len={assessment.length} < {MIN_REASON_CHARS}")
                if assessment.missing:
                    why.append("缺四要素 " + "/".join(assessment.missing))
                if assessment.stop_ts is not None:
                    prov = f"{assessment.stop_source}={assessment.stop_ts.isoformat()}"
                    tail = (
                        "历史停用 ⇒ LEGACY 迁移窗口"
                        if assessment.legacy
                        else "停用不早于 cutoff ⇒ 不豁免"
                    )
                else:
                    prov = "无 paused_at/last_run_at 溯源"
                    tail = "无法证明早于 cutoff ⇒ 不豁免"
                level = LEVEL_LEGACY if assessment.legacy else LEVEL_FAIL
                findings.append(
                    (
                        RULE_DISABLED_REASON_THIN,
                        level,
                        f"{tag}: 停用理由不实质（{' · '.join(why)}；{prov}；{tail}）"
                        f"；source={assessment.source}",
                    )
                )
            continue
        deliver = str(job.get("deliver") or "")
        if deliver.startswith("local") and not str(
            job.get("local_deliver_reason") or ""
        ).strip():
            findings.append(
                (
                    RULE_ENABLED_LOCAL,
                    LEVEL_FAIL,
                    f"{tag}: 启用中但 deliver={deliver}（启用即静默；需改 deliver 或给 local_deliver_reason）",
                )
            )
        nxt = _parse_ts(job.get("next_run_at"))
        if nxt is not None and nxt < now:
            findings.append(
                (
                    RULE_ENABLED_FROZEN,
                    LEVEL_FAIL,
                    f"{tag}: 启用中但 next_run_at={nxt.isoformat()} 已过（僵尸/冻结 · 调度器不会跑它）",
                )
            )
        if _is_feishu_deliver(deliver):
            feishu_dependents.append(name)
    if feishu_dependents:
        # 单次探测（不是每 job 一次）⇒ 天然限流；默认探针另有 TTL 缓存
        result = (feishu_probe_fn or feishu_probe)() or {}
        verdict = str(result.get("verdict") or "UNKNOWN")
        level = _level_for_verdict(verdict)
        if level is not None:
            detail = f"verdict={verdict} source={result.get('source')}"
            if result.get("age_s") is not None:
                detail += f" age={result['age_s']}s"
            if result.get("http"):
                detail += f" http={result['http']}"
            if result.get("code") is not None:
                detail += f" code={result['code']}"
            if result.get("error"):
                detail += f" error={result['error']}"
            shown = ", ".join(feishu_dependents[:3])
            more = "…" if len(feishu_dependents) > 3 else ""
            findings.append(
                (
                    RULE_FEISHU_UNREACHABLE,
                    level,
                    f"飞书通道不可达（{len(feishu_dependents)} 个启用 job 依赖它：{shown}{more}）：{detail}",
                )
            )
    return findings


def _load(path: Path) -> Optional[List[Dict[str, Any]]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[cron-hygiene] UNREADABLE {path}: {exc}")
        return None
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    return jobs if isinstance(jobs, list) else []


def run(
    path: Path,
    feishu_probe_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> int:
    jobs = _load(path)
    if jobs is None:
        print(f"[cron-hygiene] SKIP (no jobs file at {path})")
        return EXIT_OK
    findings = evaluate(jobs, now=now, feishu_probe_fn=feishu_probe_fn)
    fails = [f for f in findings if f[1] == LEVEL_FAIL]
    warns = [f for f in findings if f[1] == LEVEL_WARN]
    legacy = [f for f in findings if f[1] == LEVEL_LEGACY]
    for rule, level, msg in findings:
        print(f"[cron-hygiene] {level} {rule}: {msg}")
    print(
        f"[cron-hygiene] jobs={len(jobs)} fail={len(fails)} warn={len(warns)} "
        f"legacy={len(legacy)} file={path}"
    )
    if not findings:
        print("[cron-hygiene] OK: 记账面 / 投递面 / 通道面 无一 FAIL/WARN/LEGACY")
    return EXIT_FAIL if fails else EXIT_OK


# ---------------------------------------------------------------------------
# 负控自证：坏病例（R1/R2/R3/R4×2/R5×2）+ 孪生合规对照（含迁移窗口不假红）
# ---------------------------------------------------------------------------


def _mk_job(jid: str, name: str, **over: Any) -> Dict[str, Any]:
    job: Dict[str, Any] = {
        "id": jid,
        "name": name,
        "enabled": True,
        "deliver": "feishu:oc_x",
        "next_run_at": "2999-01-01T00:00:00+00:00",
        "schedule": {"type": "cron", "value": "0 8 * * *"},
    }
    job.update(over)
    return job


def _probe_ok() -> Dict[str, Any]:
    return {"verdict": "AUTH_OK", "source": "selftest-stub"}


def _probe_never_called() -> Dict[str, Any]:
    raise AssertionError("R5 探针不该被调用（本病例无 feishu 投递依赖）")


def selftest() -> int:
    fixed_now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    cases: List[Tuple[str, List[Dict[str, Any]], Callable[[], Dict[str, Any]], List[Tuple[str, str]]]] = [
        ("bad_no_reason", [_mk_job("b1", "坏-停用无理由", enabled=False)], _probe_ok, [(RULE_DISABLED_NO_REASON, LEVEL_FAIL)]),
        ("bad_local", [_mk_job("b2", "坏-启用但 local", deliver="local")], _probe_ok, [(RULE_ENABLED_LOCAL, LEVEL_FAIL)]),
        ("bad_frozen", [_mk_job("b3", "坏-启用但冻结", next_run_at="2026-08-19T03:46:01+00:00")], _probe_ok, [(RULE_ENABLED_FROZEN, LEVEL_FAIL)]),
        (
            "bad_reason_short_new",
            [_mk_job("b4", "坏-新停用两字理由", enabled=False, disable_reason="恢复", paused_at="2026-09-21T02:00:00+00:00")],
            _probe_ok,
            [(RULE_DISABLED_REASON_THIN, LEVEL_FAIL)],
        ),
        (
            "bad_reason_short_noprov",
            [_mk_job("b5", "坏-两字理由无溯源字段", enabled=False, disable_reason="恢复")],
            _probe_ok,
            [(RULE_DISABLED_REASON_THIN, LEVEL_FAIL)],
        ),
        (
            "bad_reason_missing_new",
            [
                _mk_job(
                    "b6",
                    "坏-新停用缺四要素",
                    enabled=False,
                    disable_reason="一次性验收任务已完成（batch2 B4-b 窗口验收），保留为证据记录。",
                    paused_at="2026-09-21T02:00:00+00:00",
                )
            ],
            _probe_ok,
            [(RULE_DISABLED_REASON_THIN, LEVEL_FAIL)],
        ),
        (
            "legacy_thin_reason",
            [_mk_job("g9", "孪生-历史薄理由不假红", enabled=False, disable_reason="N13 正控完成", paused_at="2026-09-18T05:13:28+00:00")],
            _probe_ok,
            [(RULE_DISABLED_REASON_THIN, LEVEL_LEGACY)],
        ),
        (
            "bad_feishu_auth",
            [_mk_job("b7", "坏-通道认证失败")],
            lambda: {"verdict": "AUTH_ERR", "source": "injected", "code": 99991},
            [(RULE_FEISHU_UNREACHABLE, LEVEL_FAIL)],
        ),
        (
            "bad_feishu_transport",
            [_mk_job("b8", "坏-通道传输失败")],
            lambda: {"verdict": "TRANSPORT_ERR", "source": "injected", "error": "URLError"},
            [(RULE_FEISHU_UNREACHABLE, LEVEL_WARN)],
        ),
        (
            "bad_feishu_no_creds",
            [_mk_job("b9", "坏-通道无凭据")],
            lambda: {"verdict": "NO_CREDENTIALS", "source": "injected"},
            [(RULE_FEISHU_UNREACHABLE, LEVEL_FAIL)],
        ),
        ("twin_ok_enabled_feishu", [_mk_job("g1", "孪生-启用且 feishu")], _probe_ok, []),
        ("twin_ok_disabled_stamped", [_mk_job("g2", "孪生-停用理由带四要素", enabled=False, disable_reason="谁=Mimir 何时=2026-09-21 为何=任务闭环 可逆转=enabled+deliver")], _probe_ok, []),
        ("twin_ok_local_exempt", [_mk_job("g3", "孪生-local 有豁免", deliver="local", local_deliver_reason="runner 只落台账")], _probe_never_called, []),
        ("twin_ok_probe_off", [_mk_job("g4", "孪生-通道未测不假红")], lambda: {"verdict": "SKIPPED", "source": "env-off"}, []),
    ]
    ok = True
    saved = os.environ.get("MIMIR_CRON_HYGIENE_REASON_CUTOFF")
    os.environ["MIMIR_CRON_HYGIENE_REASON_CUTOFF"] = REASON_STANDARD_CUTOFF.isoformat()
    try:
        for label, jobs, probe, expect in cases:
            got = sorted({(r, lvl) for r, lvl, _m in evaluate(jobs, now=fixed_now, feishu_probe_fn=probe)})
            want = sorted(set(expect))
            good = got == want
            ok = ok and good
            print(f"[selftest] {'PASS' if good else 'FAIL'} {label}: 期望 {want or '-'} / 实得 {got or '-'}")
    finally:
        if saved is None:
            os.environ.pop("MIMIR_CRON_HYGIENE_REASON_CUTOFF", None)
        else:
            os.environ["MIMIR_CRON_HYGIENE_REASON_CUTOFF"] = saved
    print(f"[selftest] {'ALL PASS' if ok else 'HAS FAILURE'}")
    return EXIT_OK if ok else EXIT_FAIL


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Cron 记账卫生闸（只读）")
    ap.add_argument("--jobs-file", default=None, help="jobs.json 路径（默认 MIMIR_HOME/cron/jobs.json）")
    ap.add_argument("--selftest", action="store_true", help="跑合成负控/孪生对照（不联网）")
    ap.add_argument("--no-net", action="store_true", help="本次关闭 R5 网络动作（等价 MIMIR_CRON_HYGIENE_NET=0）")
    args = ap.parse_args(argv)
    if args.no_net:
        os.environ["MIMIR_CRON_HYGIENE_NET"] = "0"
    if args.selftest:
        return selftest()
    return run(Path(args.jobs_file) if args.jobs_file else default_jobs_file())


if __name__ == "__main__":
    sys.exit(main())
