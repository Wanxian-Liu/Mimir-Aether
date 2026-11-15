"""蒸馏增量信号回归（2026-11-16）。

护的是什么事故
--------------
投递报告原为 `key_decisions: {old} → {new} ({old - new:+d})`：
① 差值方向反了（old-new，应为 new-old）；
② 只看**条数**，对内容变化完全失明 —— 等长替换（20→20 但全换）显示 `(+0)`。
实证：10-24→11-15 共 172 次注入只有 1 种 id 组合（内容真冻结），
但即使某晚内容全变、条数不变，旧报告依然报 `(+0)` ⇒ 唯一日读信号无法区分
「没变」与「全变了但条数相同」。

变异点（关键）
-------------
若把实现改回「只比 len()」，`test_equal_length_replacement_detected` 必失败
（等长替换时 len 差 = 0）。这条用例就是防这个退化。
"""
import pytest

from agent.dream_memory import _diff_memory_arrays, _delta_alert, memory_id


def test_equal_length_replacement_detected():
    """变异点：等长替换必须被识别（len 差为 0，身份差为 1+1）。"""
    old_kd = [{"decision": "决策甲"}]
    new_kd = [{"decision": "决策乙"}]
    assert len(old_kd) == len(new_kd)  # 长度差 = 0，正是旧实现会漏报的形态
    d = _diff_memory_arrays(old_kd, [], new_kd, [])
    assert len(d["key_decisions"]["added"]) == 1
    assert len(d["key_decisions"]["removed"]) == 1
    assert d["key_decisions"]["kept"] == 0


def test_identical_arrays_yield_zero_and_alert():
    """负控：内容不变 ⇒ added=0 removed=0 ⇒ 必须出告警横幅。"""
    same = [{"decision": "决策甲"}, {"decision": "决策乙"}]
    d = _diff_memory_arrays(same, same, same, same)
    assert d["key_decisions"]["added"] == []
    assert d["key_decisions"]["removed"] == []
    assert d["key_decisions"]["kept"] == 2
    alert = _delta_alert(d)
    assert alert.startswith("[ALERT]")
    assert "零增" in alert


def test_change_suppresses_alert():
    """正控：内容有变 ⇒ 不得出告警（防「恒告警」= 噪音闸）。"""
    d = _diff_memory_arrays([{"decision": "决策甲"}], [], [{"decision": "决策丙"}], [])
    assert _delta_alert(d) == ""


def test_identity_is_content_based_not_position():
    """顺序变化不算变化：memory_id 按文本哈希（文本即身份）。"""
    a = [{"decision": "决策甲"}, {"decision": "决策乙"}]
    b = [{"decision": "决策乙"}, {"decision": "决策甲"}]
    d = _diff_memory_arrays(a, a, b, b)
    assert d["key_decisions"]["added"] == []
    assert d["key_decisions"]["removed"] == []
    assert d["key_decisions"]["kept"] == 2


def test_removed_text_is_captured_for_audit():
    """被删条目必须留下文本前段（否则只知数量、不知删了什么）。"""
    d = _diff_memory_arrays([{"decision": "被删掉的旧决策"}], [], [], [])
    assert len(d["key_decisions"]["_removed_text"]) == 1
    assert "被删掉的旧决策" in d["key_decisions"]["_removed_text"][0]


def test_patterns_line_counted_independently():
    """kd 与 lp 各自计数，不得互相掩盖。"""
    d = _diff_memory_arrays(
        [{"decision": "甲"}], [{"pattern": "旧模式"}], [{"decision": "甲"}], [{"pattern": "新模式"}]
    )
    assert d["key_decisions"]["added"] == []
    assert len(d["learned_patterns"]["added"]) == 1
    assert _delta_alert(d) == ""  # lp 有变化 ⇒ 不告警


def test_memory_id_contract_is_whitespace_collapse_not_removal():
    """memory_id 的**真实**契约：`_norm_mem_text` = `" ".join(str(v).split())`。

    即「连续空白压平为单个空格」，**不是**删空白、**不是**大小写/标点归一。
    （写本用例时我一度按「删空白」假设写，实测立刻失败 —— 记在此防复发。）
    差分依赖这一点：只有回车/多空格被重排不会误报，而「有空格 vs 无空格」会算作真变化。
    """
    assert memory_id("决策   甲") == memory_id("决策 甲")     # 连续空白压平
    assert memory_id("决策\n\t甲") == memory_id("决策 甲")  # 换行制表符同
    assert memory_id("决策 甲") != memory_id("决策甲")       # 空格 vs 无空格 = 不同身份
    assert memory_id("Decision A") != memory_id("decision a")  # 非大小写归一
