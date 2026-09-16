"""F2-c 补样台账闸（2026-09-16）：把终裁③ 的口径与两条实测坑变成可回归判据。

坑（本轮实测）：
  ① **嵌套 HOME 骗过判据**：`Path.home()/".mimiraether"` 在本机得到嵌套假路径，而该目录**真的存在**
     （早先事故产物）⇒ 旧写法「logs 目录存在即用」被骗过 ⇒ 扫到 0 事件（`events=0` 看着像「没事件」）
  ② **跨日志重复计数**：`errors.log` 镜像 `gateway.log` 的部分行 ⇒ 不去重会把同一事件算成
     「1 条配对 + 1 条孤儿」，n 虚高、比例失真（实测 13 → 10 事件）
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load():
    path = SCRIPTS / "f2c_sample_ledger.py"
    spec = importlib.util.spec_from_file_location("f2c_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LINE_BEGIN = ("2026-09-16 10:15:54,638 INFO gateway.session: [INDEX] hygiene-compress "
              "begin sid=S1 docs=4 timeout_s=300.0")
LINE_END = ("2026-09-16 10:16:19,563 INFO gateway.session: [INDEX] hygiene-compress "
            "end sid=S1 docs=4 elapsed=24.93s")
LINE_TIMEOUT = ("2026-09-16 10:20:00,000 WARNING gateway.session: [INDEX] hygiene-compress "
                "TIMEOUT sid=S1 docs=48 elapsed=300.00s limit=300.0s -- worker abandoned")


def _mk(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_dedup_across_mirrored_logs(tmp_path):
    """② errors.log 镜像同一条 TIMEOUT ⇒ 不得双边计数。"""
    m = _load()
    g = _mk(tmp_path, "gateway.log", [LINE_BEGIN, LINE_TIMEOUT])
    e = _mk(tmp_path, "errors.log", [LINE_TIMEOUT])          # 镜像行
    events, notes = m.read_events([g, e])
    assert len(events) == 2, events
    assert any(n.startswith("dedup:") for n in notes)
    runs, orphans = m.pair_runs(events)
    assert len(runs) == 1 and runs[0]["outcome"] == "timeout"
    assert orphans == []


def test_incidents_merge_same_sid_within_gap(tmp_path):
    """唯一事件 = 同 sid 间隔 <= gap 归并；异 sid 不并。"""
    m = _load()
    lines = []
    for hh, mm in ((10, 0), (10, 16), (10, 32)):            # 同 sid，间隔 16min
        lines.append(f"2026-09-16 {hh}:{mm:02d}:00,000 INFO gateway.session: [INDEX] "
                     f"hygiene-compress begin sid=SA docs=1 timeout_s=300.0")
        lines.append(f"2026-09-16 {hh}:{mm+10:02d}:00,000 WARNING gateway.session: [INDEX] "
                     f"hygiene-compress TIMEOUT sid=SA docs=1 elapsed=300.00s")
    lines.append("2026-09-16 12:00:00,000 INFO gateway.session: [INDEX] hygiene-compress "
                 "begin sid=SB docs=2 timeout_s=300.0")
    lines.append("2026-09-16 12:00:20,000 INFO gateway.session: [INDEX] hygiene-compress "
                 "end sid=SB docs=2 elapsed=20.00s")
    p = _mk(tmp_path, "gateway.log", lines)
    rec_events, _ = m.read_events([p])
    runs, _ = m.pair_runs(rec_events)
    inc = m.merge_incidents(runs, 45.0)
    assert len(inc) == 2, inc
    assert inc[0]["sid"] == "SA" and len(inc[0]["runs"]) == 3 and inc[0]["timeouts"] == 3
    assert inc[1]["sid"] == "SB" and len(inc[1]["runs"]) == 1
    # 归并窗的判据是「跑与跑的间隙」（finish → 下次 start = 6min），不是事件间隔 16min
    inc_tight = m.merge_incidents(runs, 5.0)
    assert sum(1 for i in inc_tight if i["sid"] == "SA") == 3, inc_tight
    assert sum(1 for i in m.merge_incidents(runs, 6.0) if i["sid"] == "SA") == 1  # 边界：恰好 6min ⇒ 仍并


def test_default_paths_prefers_dir_that_actually_has_logs(tmp_path, monkeypatch):
    """① 嵌套假路径（logs 目录存在但无日志）不得被选中。"""
    m = _load()
    fake = tmp_path / ".mimiraether" / ".mimiraether"
    (fake / "logs").mkdir(parents=True)                      # 空 logs（旧 bug 的诱饵）
    real = tmp_path / ".mimiraether"
    (real / "logs").mkdir(parents=True)
    (real / "logs" / "gateway.log").write_text("x", encoding="utf-8")
    monkeypatch.setenv("MIMIR_HOME", str(real))
    paths = m.default_paths()
    assert paths[0] == real / "logs" / "gateway.log", paths


def test_wilson_bounds_and_decision_rule():
    m = _load()
    assert m.wilson(0, 0) == (0.0, 1.0)
    lo, hi = m.wilson(1, 2)
    assert 0.09 < lo < 0.10 and 0.90 < hi < 0.91, (lo, hi)
    assert m.wilson(20, 20)[0] > 0.80
    # 终裁③ 硬闸：n < min_n ⇒ 不下结论（本轮盘上实测 n=2）
    d = m.decide(2, 0.0945, 0.9055, 20, 0.05)
    assert d["verdict"] == "INSUFFICIENT" and "样本不足" in d["why"]
    # 罕见 ⇒ 降级；不罕见 ⇒ 实施；跨阈值 ⇒ 继续观测
    assert m.decide(100, 0.0, 0.01, 20, 0.05)["verdict"] == "DOWNGRADE"
    assert m.decide(100, 0.20, 0.30, 20, 0.05)["verdict"] == "IMPLEMENT"
    assert m.decide(100, 0.01, 0.20, 20, 0.05)["verdict"] == "KEEP_OBSERVING"


def test_real_logs_parse_to_expected_shape():
    """对**真实**日志跑一次：结构判据（不断言具体数字 —— 数字会随观测增长）。"""
    m = _load()
    rec = m.build(m.default_paths())
    c = rec["counts"]
    assert c["events"] >= 0 and c["runs"] == c["timeout_runs"] + (c["runs"] - c["timeout_runs"])
    assert len(rec["wilson"]["incidents"]) == 2
    assert rec["verdict"] in {"INSUFFICIENT", "IMPLEMENT", "DOWNGRADE", "KEEP_OBSERVING"}
    assert rec["rule"]["min_n"] == 20
