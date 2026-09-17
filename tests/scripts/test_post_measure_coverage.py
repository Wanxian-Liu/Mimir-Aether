"""H2 效果度量闸：`scripts/post_measure_coverage.py`。

为什么要有这个闸（而不是只看一次手跑输出）：
  H2 的「修好了」只能由**结算率**证明。如果度量脚本本身会静默返 0 / 把
  `cross_run` 和 `same_run` 混成一坨，那 H2 的效果就**不可证**。

三条硬约束（都对应本项目踩过的坑）：
  1. 目标缺失必须 **rc=2 显式失败**，不得静默返 0（假绿防护）；
  2. `settle_source` 缺失的历史行必须单独计为 `pre_h2`，不得并进新口径；
  3. 脚本必须自己注入 repo 根到 `sys.path` —— **首版就栽在这**：import 失败被
     `except` 吞掉 ⇒ 悄悄退回相对路径 ⇒ 报「file not found」，真因是 import 错。
"""
import json
import subprocess
import time
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "post_measure_coverage.py"


def _write_ledger(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    return path


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          cwd=str(REPO_ROOT), capture_output=True, text=True)


@pytest.fixture
def ledger(tmp_path):
    """3 applied + 1 rollback + 4 post_measure（same_run / cross_run / expired / pre_h2）。"""
    return _write_ledger(tmp_path / "cq.jsonl", [
        {"outcome": "applied", "original_count": 400, "compressed_count": 35},
        {"outcome": "applied", "original_count": 300, "compressed_count": 30},
        {"outcome": "applied", "original_count": 200, "compressed_count": 20},
        {"outcome": "rollback", "original_count": 100, "compressed_count": 90},
        {"kind": "post_measure", "settle_reason": "settled", "settle_source": "cross_run",
         "net_tokens": 1000},
        {"kind": "post_measure", "settle_reason": "settled", "settle_source": "same_run",
         "net_tokens": 500},
        {"kind": "post_measure", "settle_reason": "expired", "settle_source": "cross_run"},
        {"kind": "post_measure", "settle_reason": "settled"},      # 无 source ⇒ pre_h2
    ])


def test_coverage_and_source_split(ledger):
    p = _run("--ledger", str(ledger), "--json")
    assert p.returncode == 0, (p.stdout, p.stderr)
    s = json.loads(p.stdout)
    assert s["applied"] == 3                       # rollback 不算 applied
    assert s["post_rows"] == 4
    assert s["settled"] == 3                       # 两条 settled + 一条 pre_h2 settled
    assert s["coverage"] == 1.0
    assert s["settle_sources"] == {"cross_run": 2, "same_run": 1, "pre_h2": 1}
    assert s["settle_reasons"]["expired"] == 1


def test_low_coverage_exits_nonzero(ledger):
    p = _run("--ledger", str(ledger), "--min-coverage", "1.5")
    assert p.returncode == 1, p.stdout
    assert "VERDICT: LOW" in p.stdout


def test_missing_target_fails_loudly_with_rc2(tmp_path):
    """假绿防护：目标不存在 ⇒ rc=2，不许静默返 0。"""
    missing = tmp_path / "nope.jsonl"
    assert not missing.exists()
    p = _run("--ledger", str(missing))
    assert p.returncode == 2, (p.returncode, p.stdout)
    assert "not found" in p.stdout


def test_unparsable_lines_are_counted(tmp_path, ledger):
    bad = tmp_path / "mixed.jsonl"
    bad.write_text(ledger.read_text(encoding="utf-8") + "{not json}\n", encoding="utf-8")
    p = _run("--ledger", str(bad), "--json")
    assert p.returncode == 0, p.stdout
    assert json.loads(p.stdout)["unparsable_lines"] == 1


def test_no_applied_rows_is_no_applied_not_ok(tmp_path):
    led = _write_ledger(tmp_path / "empty.jsonl",
                        [{"outcome": "rollback", "original_count": 1}])
    p = _run("--ledger", str(led))
    assert p.returncode == 1
    assert "NO_APPLIED" in p.stdout


def test_script_injects_repo_root_into_sys_path():
    """结构闸：这条正是首版的真根因（import 失败被吞 ⇒ 假「file not found」）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in src
    assert "from mimir_constants import get_mimir_home" in src
    # 作用域必须收紧到**模块头**（import/path 注入区）：函数体里的
    # `except Exception:` 是正当的（JSON 解析兜底），拿它判会得假红。
    header = src.split("def load_rows")[0]
    assert "except Exception:" not in header, (
        "模块头不得把 home 解析包在 except 里静默降级（首版真根因）"
    )


# ── N4（2026-09-18）「未交未出谁认账」：认领凭据 ↔ 结算行 对账 ──────────────
def _claim(d, corr_id, age_s, pid=1234):
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.json" % corr_id)).write_text(json.dumps({
        "kind": "claim", "corr_id": corr_id,
        "claimed_at": time.time() - age_s, "claimed_at_iso": "2026-09-18T00:00:00",
        "pid": pid, "session_tag": "deadbeefdeadbeef",
    }, ensure_ascii=False), encoding="utf-8")
    return d


def test_abandoned_claim_is_reported_and_fails(ledger, tmp_path):
    """认了账、过了 grace、无结算行 ⇒ abandoned>0 ⇒ **rc=1 显式失败**（不静默）。"""
    cd = _claim(tmp_path / "claims", "corrDEAD", age_s=7200)
    p = _run("--ledger", str(ledger), "--claims-dir", str(cd), "--json")
    s = json.loads(p.stdout)
    assert s["abandoned"] == 1, s
    assert s["claims_total"] == 1 and s["claims_matched"] == 0
    assert s["abandoned_detail"][0]["corr_id"] == "corrDEAD"
    assert p.returncode == 1


def test_inflight_claim_is_not_abandoned(ledger, tmp_path):
    """刚认领、未过 grace ⇒ 算**在途**，不得读成 abandoned（否则每轮误报）。"""
    cd = _claim(tmp_path / "claims", "corrLIVE", age_s=5)
    p = _run("--ledger", str(ledger), "--claims-dir", str(cd), "--abandon-grace-s", "3600", "--json")
    s = json.loads(p.stdout)
    assert s["abandoned"] == 0 and s["claims_inflight"] == 1, s
    assert p.returncode == 0, (p.stdout, p.stderr)


def test_matched_claim_is_clean(ledger, tmp_path):
    """结算行带上同一 corr_id ⇒ 视为已交账，**abandoned 恒 0**（正常路径）。"""
    cd = _claim(tmp_path / "claims", "corrDONE", age_s=7200)
    lg = tmp_path / "cq2.jsonl"
    rows = [r for r in (json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip())]
    rows.append({"kind": "post_measure", "settle_reason": "settled",
                 "settle_source": "cross_run", "claim_corr_id": "corrDONE"})
    _write_ledger(lg, rows)
    p = _run("--ledger", str(lg), "--claims-dir", str(cd), "--json")
    s = json.loads(p.stdout)
    assert s["abandoned"] == 0 and s["claims_matched"] == 1, s


def test_missing_claims_dir_is_not_an_error(ledger, tmp_path):
    """凭据目录不存在 ⇒ 全 0（H2/N4 之前的历史环境），不得报错、不得假绿成 abandoned。"""
    p = _run("--ledger", str(ledger), "--claims-dir", str(tmp_path / "nope"), "--json")
    s = json.loads(p.stdout)
    assert s["claims_total"] == 0 and s["abandoned"] == 0
