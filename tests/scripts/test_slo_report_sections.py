"""SLO 看板 3 处读数缺陷的回归用例（2026-09-30 · 刘哥「动手」后补）。

为什么需要：三处缺陷都不是「算错」，是**读数会说谎** ——
D-1 空窗口印 `0.0`（被读成实测 0 秒）· D-2 段名自称 bootstrap CI 却从未算区间
（点估计被当因果证据）· D-3 硬编码目标串冒充对照。这类缺陷只能靠用例钉住口径。
"""

import importlib.util
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "slo_dashboard.py"
_spec = importlib.util.spec_from_file_location("slo_dashboard_under_test", SCRIPT)
slo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slo)


def _turn(sec, ts=None):
    """构造一条 turn 元组 (ts, api, ntools, total)。"""
    return (ts or datetime(2026, 9, 1, 12, 0, 0), 1.0, 1, sec)


# ---------- D-1：空窗口禁印 0.0 ----------

def test_stat_cells_empty_is_no_data_not_zero():
    """正控：空窗口 ⇒ 「无数据 / —」，且**不含** `0.0`（0.0 是有效读数，不是缺数据）。"""
    n_disp, cells = slo.stat_cells([])
    assert n_disp == "无数据"
    assert cells == ["—", "—", "—", "—"]
    assert "0.0" not in " ".join([n_disp] + cells)


def test_stat_cells_nonempty_keeps_numeric():
    """负控：有数据时必须是数字（证明「无数据」不是无条件印的）。

    口径钉（与 test_slo_efficiency_metrics 同名条款一致）：percentile 为 nearest-rank
    上界 `sorted[int(n*p/100)]` ⇒ 2 个样本时 P50 取上界 8.0，不是 4.0。首版我期望写
    4.0 = 我错、代码对 —— 用例与代码必须一起定口径。
    """
    n_disp, cells = slo.stat_cells([_turn(4.0), _turn(8.0)])
    assert n_disp == "2"
    assert cells[0] == "8.0"


def test_attribution_section_empty_window_never_prints_zero():
    """D-1 回归：③ 段空窗口行必须「无数据」，禁出现 0.0（原缺陷 :371 无守卫）。"""
    commits = [(datetime(2026, 8, 20, 10, 0, 0), "aaaaaaa", "s")]
    lines = []
    slo.attribution_section(lines, commits, [], datetime(2026, 8, 19, 2, 8, 0))
    text = "\n".join(lines)
    row = [l for l in lines if l.startswith("| `aaaaaaa`")][0]
    assert "无数据" in row
    assert "0.0" not in row, "空窗口印了 0.0 ⇒ D-1 复发"
    assert "P95 95%CI" in text, "③ 段表头必须含区间列（D-2）"


# ---------- D-2：bootstrap CI 真算且可复现 ----------

def test_bootstrap_ci_degenerates_on_constant_data():
    """正控：常量样本 ⇒ 区间必须退化为一点。"""
    lo, hi = slo.bootstrap_ci([_turn(7.0)] * 6)
    assert lo == hi == 7.0


def test_bootstrap_ci_is_not_degenerate_on_spread_data():
    """负控：分布样本 ⇒ lo < hi（否则「算了 CI」是假的，退化成点估计）。"""
    lo, hi = slo.bootstrap_ci([_turn(v) for v in (1.0, 2.0, 5.0, 9.0, 20.0, 40.0)])
    assert lo < hi, "区间退化 ⇒ 未真做重采样"
    assert lo >= 1.0 and hi <= 40.0, "区间越出样本范围 ⇒ 重采样实现有误"


def test_bootstrap_ci_same_seed_identical():
    """同 seed 两次调用读数逐字一致 ⇒ 「变化」不会被随机抖动伪造。"""
    data = [_turn(v) for v in (1.0, 3.0, 4.0, 9.0, 11.0, 30.0)]
    assert slo.bootstrap_ci(data) == slo.bootstrap_ci(data)


def test_ci_cell_marks_small_windows_unreliable():
    """窗口 < MIN_N_FOR_CI ⇒ 标不可靠，不给一个看着像结论的区间。"""
    assert slo._ci_cell([]) == "—"
    assert slo._ci_cell([_turn(1.0)]) == f"—（n=1<{slo.MIN_N_FOR_CI}）"


# ---------- D-3：对照段给实测读数，无量具的显式标无读数 ----------

def test_comparison_section_prints_live_readings(monkeypatch):
    """D-3 回归：对照三项必须逐项给当前读数，不再只印硬编码目标串。"""
    monkeypatch.setattr(slo, "_single_tool_ratio", lambda days=7: (100, 77, 77.0, 50.0))
    lines = []
    slo.comparison_section(lines, 7, [10, 20, 130])
    text = "\n".join(lines)
    assert "**77.0%**" in text and "77/100" in text, "缺实测读数 ⇒ D-3 复发"
    assert "**1 个**" in text and "❌ 未达标" in text
    assert "无读数" in text, "无量具的一项必须显式标「无读数」"


def test_comparison_section_no_window_data(monkeypatch):
    """负控：窗口无数据 ⇒ 印「无数据」，不得把 0 当成 0% 达标。"""
    monkeypatch.setattr(slo, "_single_tool_ratio", lambda days=7: (0, 0, None, 50.0))
    lines = []
    slo.comparison_section(lines, 7, [])
    text = "\n".join(lines)
    assert "无数据" in text
    assert "达标" not in text.split("无数据")[0]
