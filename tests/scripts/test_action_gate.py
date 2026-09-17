'''tests for scripts/action_gate.py — 动作层闸（P0②）

判据来源：Phase β 段8 事故（零嵌入被记为完成）。本文件把「闸必须拦住什么」
写成可执行断言；其中 fail-closed 三条（测量失败/表缺失/库缺失）是核心：
它们必须**报错**，绝不允许退化成 0 或 PASS。
'''
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from scripts import action_gate as ag  # noqa: E402


def _fixture(dirpath, embedded, name='fix.db', table=ag.DEFAULT_TABLE):
    db = os.path.join(dirpath, name)
    con = sqlite3.connect(db)
    con.execute('create table %s(rowid integer primary key autoincrement, id, chunk_id integer,'
                ' chunk_offset integer)' % (table + ag.ROWRIDS_SUFFIX))
    for r in range(1, embedded + 1):
        con.execute('insert into %s(rowid, chunk_id, chunk_offset) values (?,?,?)'
                    % (table + ag.ROWRIDS_SUFFIX), (r, 1, r))
    con.commit()
    con.close()
    return db


# ----------------------------------------------------------- 判定层（纯函数）
def test_ok_when_enough_embedded():
    r = ag.check(rc=0, todo_n=1000, measured=900)
    assert r['ok'] is True and r['reason'] == 'ok'


def test_fail_zero_embedded():
    r = ag.check(rc=0, todo_n=1000, measured=0)
    assert r['ok'] is False and r['reason'] == 'zero_embedded'


def test_fail_rc_nonzero():
    assert ag.check(rc=1, todo_n=1000, measured=1000)['reason'] == 'rc_nonzero'


def test_fail_measure_error_when_none():
    '''fail-closed：没测到 = FAIL，绝不是 PASS。'''
    r = ag.check(rc=0, todo_n=1000, measured=None)
    assert r['ok'] is False and r['reason'] == 'measure_error'


def test_fail_below_min_ratio():
    assert ag.check(rc=0, todo_n=1000, measured=400)['reason'] == 'below_min_ratio'


def test_fail_regression_and_zero_delta():
    assert ag.check(rc=0, todo_n=10, measured=9, before_n=100, after_n=99)['reason'] == 'regression'
    assert ag.check(rc=0, todo_n=10, measured=9, before_n=100, after_n=100)['reason'] == 'zero_delta'


def test_empty_todo_is_explicit_pass():
    assert ag.check(rc=0, todo_n=0, measured=0)['reason'] == 'empty_todo'


def test_allow_empty_is_explicit_escape():
    r = ag.check(rc=0, todo_n=1000, measured=0, allow_empty=True)
    assert r['ok'] is True and r['reason'] == 'zero_embedded_allowed'


def test_required_min_rounds_up():
    assert ag.required_min(1000, 0.5) == 500
    assert ag.required_min(3, 0.5) == 2


# ----------------------------------------------------------- 测量层（fail-closed）
def test_count_present_counts_real_rows():
    with tempfile.TemporaryDirectory() as d:
        db = _fixture(d, embedded=7)
        assert ag.count_present(db, list(range(1, 11))) == 7


def test_count_present_raises_on_missing_db():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ag.GateMeasureError):
            ag.count_present(os.path.join(d, 'nope.db'), [1, 2, 3])


def test_count_present_raises_on_missing_table():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, 'empty.db')
        sqlite3.connect(db).close()
        with pytest.raises(ag.GateMeasureError):
            ag.count_present(db, [1, 2, 3])


def test_measure_file_reads_array_and_dict():
    with tempfile.TemporaryDirectory() as d:
        db = _fixture(d, embedded=5)
        p1 = os.path.join(d, 'a.json')
        json.dump([1, 2, 3, 4, 5, 6], open(p1, 'w'))
        assert ag.measure_file(db, p1)['measured'] == 5
        p2 = os.path.join(d, 'b.json')
        json.dump({'rowids': [1, 2]}, open(p2, 'w'))
        assert ag.measure_file(db, p2)['measured'] == 2


# ----------------------------------------------------------- 审计层（事故复现器）
def test_audit_only_judges_completed_segments():
    '''未跑的段读 0 是正常的 —— 只有「已记为完成」的段才判失败。'''
    with tempfile.TemporaryDirectory() as d:
        db = _fixture(d, embedded=1000)
        segs = [list(range(1, 1001)), list(range(1001, 2001))]
        rep = ag.audit_segments(db=db, segments=segs, completed=[0])
        assert rep['segments_checked'] == 1 and rep['ok'] is True
        rep2 = ag.audit_segments(db=db, segments=segs, completed=[0, 1])
        assert rep2['segments_checked'] == 2 and rep2['ok'] is False
        assert rep2['rows'][1]['reason'] == 'zero_embedded'


def test_audit_reproduces_incident_shape():
    '''照段8 的形状造夹具：7 段有向量 + 1 段零向量且被记为完成 ⇒ 恰一段 FAIL。'''
    with tempfile.TemporaryDirectory() as d:
        db = _fixture(d, embedded=7000)
        segs = [list(range(i * 1000 + 1, i * 1000 + 1001)) for i in range(8)]
        rep = ag.audit_segments(db=db, segments=segs, completed=[0, 1, 2, 3, 4, 5, 6, 7])
        assert rep['failed'] == 1 and rep['rows'][-1]['segment'] == 8


# ----------------------------------------------------------- CLI 契约
def _cli(*args):
    return subprocess.run([sys.executable, '-m', 'scripts.action_gate', *args],
                          cwd=REPO, capture_output=True, text=True)


def test_cli_selftest_all_pass():
    r = _cli('selftest', '--json')
    assert r.returncode == 0
    assert json.loads(r.stdout)['all_pass'] is True


def test_cli_inline_exit_codes():
    assert _cli('inline', '--rc', '0', '--todo-n', '1000', '--measured', '900').returncode == 0
    assert _cli('inline', '--rc', '0', '--todo-n', '1000', '--measured', '0').returncode == 1
    assert _cli('inline', '--rc', '0', '--todo-n', '1000').returncode == 1


def test_cli_measure_missing_db_is_nonzero():
    r = _cli('measure', '--db', '/nonexistent-xyz.db', '--rowids-file', '/dev/null')
    assert r.returncode == 2 and 'measure_error' in r.stdout


def test_audit_measure_error_is_fail_not_ok():
    '''fail-closed 在**审计路径**同样成立：测量失败 ⇒ FAIL，不得读成「无问题」。'''
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, 'empty.db')
        sqlite3.connect(db).close()
        rep = ag.audit_segments(db=db, segments=[[1, 2, 3]], completed=[0])
        assert rep['ok'] is False
        assert rep['rows'][0]['reason'] == 'measure_error'
        assert rep['rows'][0]['measured'] is None


def test_source_has_no_swallowing_except():
    '''结构闸：本模块不得出现 except ...: pass（吞异常 = 把「探针死了」读成「确认没有」）。'''
    src = open(os.path.join(REPO, 'scripts', 'action_gate.py'), encoding='utf-8').read()
    lowered = src.replace(' ', '')
    assert 'exceptException:pass' not in lowered
    assert 'except:pass' not in lowered
    assert 'exceptGateMeasureError:pass' not in lowered


def test_cli_only_segments_overrides_completed_filter():
    '''--only-segments：显式指定段号时**不看账本 completed** —— 这正是
    「段真跑了但账本没记」与「账本记了但段是空的」两种情形都要能判的路径。'''
    with tempfile.TemporaryDirectory() as d:
        db = _fixture(d, embedded=1000)
        full = os.path.join(d, 'full.json')
        json.dump({'rowids': list(range(1, 2001))}, open(full, 'w'))
        segs = os.path.join(d, 'segs.json')
        json.dump({'completed_segments': []}, open(segs, 'w'))
        r = _cli('audit', '--db', db, '--segments-file', segs, '--full-list', full,
                 '--only-segments', '1', '--json')
        rep = json.loads(r.stdout)
        assert rep['segments_checked'] == 1 and rep['ok'] is True
        r2 = _cli('audit', '--db', db, '--segments-file', segs, '--full-list', full,
                  '--only-segments', '2', '--json')
        assert json.loads(r2.stdout)['ok'] is False
        # 对照：不给 --only-segments 且账本为空 ⇒ 无可判段（vacuous，但显式 ok）
        r3 = _cli('audit', '--db', db, '--segments-file', segs, '--full-list', full, '--json')
        assert json.loads(r3.stdout)['segments_checked'] == 0


# ------------------------------------------- 断点重跑（reason=no_op_already_complete）
def test_no_op_already_complete_passes():
    '''expected_n 显式 == 0（本轮应做 0 条）且 before==after ⇒ PASS，不是 zero_delta。

    事故形状：段内 rowid 清单非空（todo_n > 0），但上一轮已全部嵌入并落盘 ⇒
    重跑本轮增量天然为 0，旧口径判 zero_delta ⇒ 把「已完成」读成「退化」，重跑被拦死。
    '''
    r = ag.check(rc=0, todo_n=1000, measured=1000, before_n=1000, after_n=1000,
                 expected_n=0)
    assert r['ok'] is True and r['reason'] == 'no_op_already_complete'
    assert r['increment_min'] == 0


def test_no_op_requires_explicit_expected_n():
    '''向后兼容：不给 expected_n 时零增量仍判 zero_delta（未声明 ⇒ 不许静默放行）。'''
    r = ag.check(rc=0, todo_n=1000, measured=1000, before_n=1000, after_n=1000)
    assert r['ok'] is False and r['reason'] == 'zero_delta'


def test_no_op_does_not_mask_regression():
    '''负控：expected_n=0 不是后门 —— 向量真变少（after < before）仍 FAIL regression。'''
    r = ag.check(rc=0, todo_n=1000, measured=1000, before_n=1000, after_n=999,
                 expected_n=0)
    assert r['ok'] is False and r['reason'] == 'regression'


def test_no_op_does_not_mask_measure_error():
    '''fail-closed 不破：expected_n=0 也不能把「没测到」或 rc!=0 读成 PASS。'''
    assert ag.check(rc=0, todo_n=1000, measured=None, before_n=1000, after_n=1000,
                    expected_n=0)['reason'] == 'measure_error'
    assert ag.check(rc=1, todo_n=1000, measured=1000, before_n=1000, after_n=1000,
                    expected_n=0)['reason'] == 'rc_nonzero'


def test_cli_inline_no_op_already_complete_exit0():
    '''CLI 契约：断点重跑命令行 ⇒ exit 0 且 reason 为新reason。'''
    r = _cli('inline', '--rc', '0', '--todo-n', '1000', '--measured', '1000',
             '--before-n', '1000', '--after-n', '1000', '--expected-n', '0')
    assert r.returncode == 0 and 'no_op_already_complete' in r.stdout
    # 对照：同一组数字但不声明 --expected-n ⇒ 仍非 0（zero_delta）
    r2 = _cli('inline', '--rc', '0', '--todo-n', '1000', '--measured', '1000',
              '--before-n', '1000', '--after-n', '1000')
    assert r2.returncode == 1 and 'zero_delta' in r2.stdout


def test_zero_embedded_reported_over_zero_delta_when_both_zero():
    '''原因粒度：measured=0 且增量=0 ⇒ 报更具体的 zero_embedded（事故签名），不是 zero_delta。

    当日实测（旧判定序）：接线传 before/after 后 seg8 事故路径拿到 reason=zero_delta，
    事故签名被「零增量」掩盖。两臂都 FAIL（安全不变），本条锁 reason 粒度。
    '''
    r = ag.check(rc=0, todo_n=1000, measured=0, before_n=0, after_n=0)
    assert r['ok'] is False and r['reason'] == 'zero_embedded'
    # 对照：表非空但增量 0 ⇒ 仍是 zero_delta（未把两种情况合并）
    r2 = ag.check(rc=0, todo_n=1000, measured=900, before_n=900, after_n=900)
    assert r2['ok'] is False and r2['reason'] == 'zero_delta'


# ------------------------- P0② 补齐：4 条新臂的 pytest 形式（Loki 反对① · 与 selftest 同等保护）
# 纪律：每例必须断言 ``reason``（语义），不能只看 ``ok`` 极性——极性对而语义错照样假绿。
def test_table_empty_is_distinct_from_missing_and_zero(tmp_path):
    """三种不同的 0 必须可分：表全空 / 表缺失 / 表非空但查不到。"""
    db_empty = _fixture(str(tmp_path), 0, name='empty.db')
    with pytest.raises(ag.GateTableEmpty):
        ag.count_present(db_empty, [1, 2, 3])
    # 表不存在 ⇒ 只落到父类（measure_error 层），不得被读成 table_empty
    missing_db = os.path.join(str(tmp_path), 'nope.db')
    with pytest.raises(ag.GateMeasureError) as mi:
        ag.count_present(missing_db, [1])
    assert not isinstance(mi.value, ag.GateTableEmpty)
    # 表非空、所查 rowid 全不在 ⇒ 计数 0 ⇒ 才是 zero_embedded
    db_sparse = _fixture(str(tmp_path), 50, name='sparse.db')
    assert ag.count_present(db_sparse, list(range(1001, 1101))) == 0
    assert ag.check(rc=0, todo_n=100, measured=0)['reason'] == 'zero_embedded'
    # 判定序：table_empty 先于 measure_error / zero_embedded
    assert ag.check(rc=0, todo_n=10, measured=None, table_empty=True)['reason'] == 'table_empty'
    assert ag.check(rc=0, todo_n=10, measured=0, table_empty=True)['reason'] == 'table_empty'


def test_demo_shadow_local_no_vec0(tmp_path):
    """本机可独立复现：stdlib 造普通表（无 vec0 扩展）也能跑通该读取路径。"""
    db = _fixture(str(tmp_path), 10, name='demo_shadow.db')
    rids = [2, 4, 6, 8]
    assert ag.count_present(db, rids) == 4
    r = ag.check(rc=0, todo_n=len(rids), measured=ag.count_present(db, rids))
    assert r['ok'] is True and r['reason'] == 'ok'


def test_insufficient_increment_reason(tmp_path):
    """闸 8 · increment 度量：显式 expected_n ⇒ 门槛 1.0（零缺失），增量为 after-before。"""
    r = ag.check(rc=0, todo_n=1000, measured=900, before_n=0, after_n=999, expected_n=1000)
    assert r['ok'] is False and r['reason'] == 'insufficient_increment'
    assert r['gate_mode'] == 'increment' and r['increment_min'] == 1000
    # 增量正好等于「应做」⇒ 不误杀（边界）
    edge = ag.check(rc=0, todo_n=1000, measured=1000, before_n=0, after_n=1000,
                    expected_n=1000)
    assert edge['reason'] == 'ok'


def test_direct_mode_gate8_production_shape():
    """闸 8 · direct 度量（**生产唯一可用**）：只给 measured + expected_n ⇒ 零缺失，缺一即 FAIL。"""
    short = ag.check(rc=0, todo_n=1000, measured=900, expected_n=1000)
    assert short['ok'] is False and short['reason'] == 'insufficient_increment'
    assert short['gate_mode'] == 'direct' and short['increment_min'] == 1000
    full = ag.check(rc=0, todo_n=1000, measured=1000, expected_n=1000)
    assert full['ok'] is True and full['reason'] == 'ok'


def test_expected_n_absent_is_backward_compatible():
    """闸 8 缺省不判：老调用点（只给 before/after）行为完全不变。"""
    r = ag.check(rc=0, todo_n=1000, measured=900, before_n=0, after_n=100)
    assert r['reason'] == 'ok' and 'increment_min' not in r
