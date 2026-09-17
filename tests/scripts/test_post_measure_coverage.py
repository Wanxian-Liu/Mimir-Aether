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
