'''action_gate.py - 动作层闸（P0② · Phase β 段8 事故的机制化修复）

调用方式：python3 -m scripts.action_gate ...（走 venv python，无需 shebang）

背景（真实事故 · 2026-09-15/16）
--------------------------------------------------
build_phase_beta.py:107-108 的记账条件是 rc == 0：

    rc = alpha.main()
    if rc != 0: return
    state['completed_segments'].append(seg_idx)
    state['completed_rowids'] += todo_this      # 记的是「待做清单」，不是「真做了」

段8 在零嵌入的情况下 rc=0，被记为完成，续跑按 completed_segments 选段
⇒ 该段 1000 条 rowid 永久跳过（其中 842 条本可嵌）。

W-beta2（chain 的 consistent=False ⇒ NEED_HUMAN）没拦住，因为它在账本层：
checkpoint 早已写进 phase_b_segments.json。⇒ 账本层断言 ≠ 动作层闸门。

本模块 = 动作层闸：不看 rc、不看日志、不看账本，只看数据库里真的有没有那些向量，
且任何测量失败一律 FAIL（fail-closed：没输出有三种意思 —— 不存在 / 没匹配 /
探针死了；本闸必须区分三者，绝不把第三种读成 PASS）。

证据通道
--------------------------------------------------
向量表是 sqlite-vec 虚表（wiki_chunks_prefix / wiki_chunks_content），
没有 vec0 扩展时连 count(*) 都读不了（实测 no such module: vec0）。
但 vec0 的影子表 <表名>_rowids 是普通表，stdlib sqlite3 直接可读
⇒ 本闸走影子表，零依赖。

判定口径（四种「零」+ 两种「零增量」）
--------------------------------------------------
「0」在本闸里是四个互不可混的结论 —— 段8 事故正是它们混装的结果：

    库打不开 / 表不存在 / 表名非法 / SQL 报错 / 探针死了 ⇒ GateMeasureError
                                                        ⇒ reason=measure_error    (FAIL)
    表存在、但表内一条都没有                             ⇒ GateTableEmpty
                                                        ⇒ reason=table_empty      (FAIL)
    表非空、所查 rowid 确实不在里面                       ⇒ measured=0
                                                        ⇒ reason=zero_embedded    (FAIL；
                                                          仅 --allow-empty 可显式放行)
    待做清单本身为空                                     ⇒ todo_n=0
                                                        ⇒ reason=empty_todo       (PASS)

「增量 = 0」有两种，语义相反，必须分开：

    zero_delta              调用方**没说**本轮该做多少，却一条也没多          ⇒ FAIL
    no_op_already_complete  调用方**显式**声明 --expected-n 0（本轮应做 0 条）
                            且 after_n == before_n                          ⇒ PASS

后者修的是「断点重跑」假 FAIL：上一轮已把该段做完并落盘，重跑时段的 rowid 清单非空
（todo_n > 0）、但本轮确实无需新增任何向量 ⇒ 增量天然为 0，旧口径判 zero_delta ⇒
把「已经完成」读成「退化了」，重跑被自己的闸拦死。**判据是调用方的显式声明**，
不是「测得 0 即通过」：expected_n 不给时 zero_delta 照旧 FAIL（向后兼容不破）。

优先级（先到先判，无「默认放行」分支）：
    rc_nonzero → table_empty → measure_error → invalid_todo_n → invalid_measured →
    empty_todo → regression → zero_embedded → no_op_already_complete → zero_delta →
    insufficient_increment → below_min_ratio → ok

regression（after < before，向量变少）优先于 no_op ⇒ 声明 expected_n=0 吞不掉真回退。
zero_embedded（measured=0）同样优先于 no_op/zero_delta ⇒ 声明 expected_n=0 也吞不掉
「一条都没嵌」；两臂都 FAIL，差别只在 reason 粒度（事故签名必须报得出来）。

用法
--------------------------------------------------
    python3 -m scripts.action_gate measure --db DB --rowids-file IDS.json
    python3 -m scripts.action_gate inline  --rc 0 --todo-n 1000 --measured 864
    python3 -m scripts.action_gate audit   --db DB --segments-file S.json --full-list F.json
    python3 -m scripts.action_gate selftest
    # 断点重跑（本轮应做 0 条）⇒ ok=True reason=no_op_already_complete，而非 zero_delta：
    python3 -m scripts.action_gate inline --rc 0 --todo-n 1000 --measured 1000 \
            --before-n 1000 --after-n 1000 --expected-n 0

退出码：0 = PASS · 1 = FAIL（闸拒绝） · 2 = 用法/测量错误（非 0 ⇒ fail-closed）
'''
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import tempfile
from typing import Any, Iterable, Sequence

GATE_VERSION = 'action-gate.v1'
# 退化阈值。依据（盘上 7 段嵌入率复算）：均值 0.910 · std 0.080 ⇒
#   0.5  = 均值 −5.12σ（只判「断崖式退化」= 日常退化拦不住；Loki P0②-4 反对②）
#   0.75 = 均值 −2σ（默认；仍宽松，只拦断崖）
# 旧值回退：env MIMIR_ACTION_GATE_MIN_RATIO=0.5
DEFAULT_MIN_RATIO = float(os.environ.get('MIMIR_ACTION_GATE_MIN_RATIO', '0.75'))
DEFAULT_TIMEOUT_S = 30.0
ROWRIDS_SUFFIX = '_rowids'
DEFAULT_TABLE = 'wiki_chunks_prefix'


class GateMeasureError(RuntimeError):
    '''测量失败 —— 必须向上冒泡成 FAIL，绝不允许被读成 PASS。'''


class GateTableEmpty(GateMeasureError):
    '''表存在、但表内一条都没有 —— 与「表不存在」「探针死了」是**三种不同的 0**。

    补 Loki P0②-5 反对③（零的第三种歧义：count(*)=0 三义混装）。
    继承 GateMeasureError ⇒ 旧调用点（只 catch 父类）行为不变，fail-closed 不破。
    '''


def rowids_table_for(table: str) -> str:
    return table if table.endswith(ROWRIDS_SUFFIX) else table + ROWRIDS_SUFFIX


def count_present(db: str, rowids: Iterable[int], table: str = DEFAULT_TABLE) -> int:
    '''数 rowids 里有多少条在 <table>_rowids 中真实存在。

    fail-closed：文件不存在 / 表不存在 / SQL 报错 / 结果不可解析 ⇒ GateMeasureError。
    绝不返回 0 来表示失败（0 与「确认没有」必须可区分）。
    '''
    rids = [int(r) for r in rowids]
    if not rids:
        return 0
    if not os.path.exists(db):
        raise GateMeasureError('db not found: %s' % db)
    tbl = rowids_table_for(table)
    if not tbl.replace('_', '').isalnum():
        raise GateMeasureError('illegal table name: %r' % tbl)
    try:
        con = sqlite3.connect('file:%s?mode=ro' % db, uri=True, timeout=DEFAULT_TIMEOUT_S)
    except sqlite3.Error as exc:
        raise GateMeasureError('open failed: %s' % exc) from exc
    try:
        have = con.execute(
            'select name from sqlite_master where type=? and name=?', ('table', tbl)
        ).fetchone()
        if not have:
            raise GateMeasureError('table missing: %s' % tbl)
        total_row = con.execute('select count(*) from %s' % tbl).fetchone()
        if total_row is None:
            raise GateMeasureError('count query returned no row: %s' % tbl)
        if int(total_row[0]) == 0:
            raise GateTableEmpty('table exists but empty: %s' % tbl)
        n = 0
        chunk = 900
        for i in range(0, len(rids), chunk):
            part = rids[i:i + chunk]
            q = 'select count(*) from %s where rowid in (%s)' % (tbl, ','.join('?' * len(part)))
            row = con.execute(q, part).fetchone()
            if row is None:
                raise GateMeasureError('count query returned no row')
            n += int(row[0])
        return n
    except sqlite3.Error as exc:
        raise GateMeasureError('query failed: %s' % exc) from exc
    finally:
        con.close()


def measure_file(db: str, rowids_file: str, table: str = DEFAULT_TABLE) -> dict:
    try:
        raw = json.load(open(rowids_file, encoding='utf-8'))
    except Exception as exc:
        raise GateMeasureError('rowids file unreadable: %s' % exc) from exc
    if isinstance(raw, dict):
        raw = raw.get('rowids', [])
    if not isinstance(raw, list):
        raise GateMeasureError('rowids file must be a JSON array (or dict with rowids)')
    total = len(raw)
    n = count_present(db, raw, table)
    return {
        'gate_version': GATE_VERSION,
        'db': db,
        'table': rowids_table_for(table),
        'todo_n': total,
        'measured': n,
        'share': (round(n / total, 6) if total else None),
    }


def required_min(todo_n: int, min_ratio: float) -> int:
    return int(math.ceil(max(0.0, min_ratio) * todo_n))


def check(*, rc: int = 0, todo_n: int, measured: Any, before_n: Any = None,
          after_n: Any = None, min_ratio: float = DEFAULT_MIN_RATIO,
          allow_empty: bool = False, table_empty: bool = False,
          expected_n: Any = None) -> dict:
    '''动作层判定。顺序即优先级；任一条命中即 FAIL（无「默认放行」分支）。

    table_empty: 表存在但全空（由 count_present 抛 GateTableEmpty 后置位）⇒
                 reason ``table_empty``，先于 ``measure_error`` / ``zero_embedded``。
    expected_n:  **可选**闸 8 —— 本轮「应增量」。给了才判：增量 < ceil(expected_n×min_ratio)
                 ⇒ ``insufficient_increment``（与 ``zero_delta`` 不同轴：增量不足 ≠ 零增量）。
                 不给则完全不判（严格向后兼容）。
                 **特例 expected_n == 0**：显式声明「本轮应做 0 条」且 ``after_n == before_n``
                 ⇒ PASS ``no_op_already_complete``（断点重跑：上轮已做完，本轮无需新增），
                 **先于** ``zero_delta`` 判定 —— 否则重跑吃假 FAIL。仍要求测量成功
                 （measured 非 None/负数，否则 measure_error/invalid_measured 先拦），
                 且 ``regression``（after < before）优先级更高：声明 expected_n=0 也吞不掉真回退。
    '''
    req = required_min(todo_n, min_ratio)
    out = {
        'gate_version': GATE_VERSION,
        'rc': rc,
        'todo_n': todo_n,
        'measured': measured,
        'required_min': req,
        'min_ratio': min_ratio,
        'allow_empty': bool(allow_empty),
        'before_n': before_n,
        'after_n': after_n,
        'table_empty': bool(table_empty),
        'expected_n': expected_n,
    }

    def verdict(ok: bool, reason: str) -> dict:
        out['ok'] = ok
        out['reason'] = reason
        return out

    if rc != 0:
        return verdict(False, 'rc_nonzero')
    if table_empty:
        return verdict(False, 'table_empty')
    if measured is None:
        return verdict(False, 'measure_error')
    if todo_n < 0:
        return verdict(False, 'invalid_todo_n')
    measured = int(measured)
    if measured < 0:
        return verdict(False, 'invalid_measured')
    if todo_n == 0:
        return verdict(True, 'empty_todo')
    if before_n is not None and after_n is not None and int(after_n) < int(before_n):
        return verdict(False, 'regression')
    if measured == 0:
        # 更具体者优先：一条都没嵌（事故签名）必须先于「零增量」报出 —— 否则开闸 8
        # 后真事故会被标成 zero_delta（读者据卡面会读成「增量不足」，掩盖事故签名）。
        # 置于 no_op / zero_delta 之前 ⇒ 声明 expected_n=0 也吞不掉真零嵌入（fail-closed）。
        if allow_empty:
            return verdict(True, 'zero_embedded_allowed')
        return verdict(False, 'zero_embedded')
    if (expected_n is not None and before_n is not None and after_n is not None
            and int(expected_n) == 0 and int(after_n) == int(before_n)):
        # 断点重跑 / already-complete：调用方显式声明「本轮应做 0 条」且确实一条没少
        # （after == before）⇒ 不是退化，是「无事可做」。必须先于 zero_delta 判，
        # 否则重跑必然吃假 FAIL；measured 已在上面过完 measure_error 闸 ⇒ fail-closed 不破。
        out['increment_min'] = 0
        return verdict(True, 'no_op_already_complete')
    if before_n is not None and after_n is not None and int(after_n) == int(before_n):
        if not allow_empty:
            return verdict(False, 'zero_delta')
    if expected_n is not None and before_n is not None and after_n is not None:
        got_inc = int(after_n) - int(before_n)
        want_inc = required_min(int(expected_n), min_ratio)
        out['increment_min'] = want_inc
        if got_inc < want_inc:
            return verdict(False, 'insufficient_increment')
    if measured < req:
        return verdict(False, 'below_min_ratio')
    return verdict(True, 'ok')


def audit_segments(*, db: str, segments: Sequence[Sequence[int]], completed: Iterable[int],
                   table: str = DEFAULT_TABLE, min_ratio: float = DEFAULT_MIN_RATIO,
                   allow_empty: bool = False, only: Iterable[int] = None) -> dict:
    '''逐段核真。只判「已记为完成」的段 —— 未跑的段读 0 是正常的，不是失败。

    这正是零的第三种歧义：段8..21 的 0 是「还没跑」，段8 当时的 0 是
    「跑了但没产出」。区分它们需要账本 + 时间点，不能只看计数。
    '''
    if only:
        done = set(int(x) - 1 for x in only)
    else:
        done = set(int(x) for x in completed)
    rows = []
    for idx, seg in enumerate(segments):
        if idx not in done:
            continue
        seg_list = [int(x) for x in seg]
        detail = None
        empty_tbl = False
        try:
            n = count_present(db, seg_list, table)
        except GateTableEmpty as exc:
            n = None
            detail = str(exc)
            empty_tbl = True
        except GateMeasureError as exc:
            n = None
            detail = str(exc)
        res = check(rc=0, todo_n=len(seg_list), measured=n, min_ratio=min_ratio,
                    allow_empty=allow_empty, table_empty=empty_tbl)
        row = {
            'segment': idx + 1,
            'todo_n': len(seg_list),
            'measured': n,
            'share': (round(n / len(seg_list), 6) if (n is not None and seg_list) else None),
            'ok': res['ok'],
            'reason': res['reason'],
            'required_min': res['required_min'],
        }
        if detail:
            row['detail'] = detail
        rows.append(row)
    failed = [r for r in rows if not r['ok']]
    return {
        'gate_version': GATE_VERSION,
        'db': db,
        'table': rowids_table_for(table),
        'segments_checked': len(rows),
        'failed': len(failed),
        'ok': not failed,
        'rows': rows,
    }


def audit_from_files(db: str, segments_file: str, full_list: str, *, seg_size: int = 1000,
                     table: str = DEFAULT_TABLE, min_ratio: float = DEFAULT_MIN_RATIO,
                     allow_empty: bool = False, only: Iterable[int] = None) -> dict:
    st = json.load(open(segments_file, encoding='utf-8'))
    full = json.load(open(full_list, encoding='utf-8'))
    if isinstance(full, dict):
        full = full.get('rowids', [])
    segs = [full[i:i + seg_size] for i in range(0, len(full), seg_size)]
    return audit_segments(db=db, segments=segs, completed=st.get('completed_segments', []),
                          table=table, min_ratio=min_ratio, allow_empty=allow_empty, only=only)


def _make_fixture(dirpath: str, embedded: int, table: str = DEFAULT_TABLE,
                  name: str = 'fix.db') -> str:
    '''造一个含 vec0 影子表结构的合成库；embedded 条有向量。

    注意：同目录第二次调用必须给不同的 name —— 否则撞 table already exists
    （本模块首版即踩此坑：两臂共用 fix.db）。
    '''
    db = os.path.join(dirpath, name)
    con = sqlite3.connect(db)
    con.execute('create table %s(rowid integer primary key autoincrement, id, chunk_id integer,'
                ' chunk_offset integer)' % (table + ROWRIDS_SUFFIX))
    for r in range(1, embedded + 1):
        con.execute('insert into %s(rowid, chunk_id, chunk_offset) values (?,?,?)'
                    % (table + ROWRIDS_SUFFIX), (r, 1, r))
    con.commit()
    con.close()
    return db


def selftest() -> dict:
    '''P/N 双控自检：合成夹具 + **十六条**判定臂。

    含 Loki P0② 方法学审三条反对的对应臂：
      反对① → ``P_demo_shadow``：stdlib sqlite3 **现造**普通表（无 vec0 扩展）跑通 ⇒
               该读取路径**本机可独立复现**，不依赖任何装了 vec0 的生产库。
      反对③ → ``N_table_empty`` vs ``N_zero_embedded_sparse``：把「表全空」与
               「表非空但所查 rowid 不在」**分成两个 reason**（零的第三种歧义）。
      闸 8  → ``N_insufficient_increment``（增量不足）+ ``P_expected_n_absent``（缺省不判）。
      闸 8·零增量 → ``P_no_op_already_complete``（expected_n==0 且增量==0 ⇒ PASS，
              修「断点重跑被 zero_delta 假 FAIL」）+ ``N_no_op_not_masking_regression``
              （负控：声明零增量**不吞**真回退 —— after<before 仍 FAIL regression）。
    '''
    arms = []
    with tempfile.TemporaryDirectory() as d:
        db_ok = _make_fixture(d, embedded=900, name='fix_ok.db')
        db_zero = _make_fixture(d, embedded=0, name='fix_zero.db')
        db_sparse = _make_fixture(d, embedded=50, name='fix_sparse.db')
        db_demo = _make_fixture(d, embedded=10, name='fix_demo_shadow.db')
        db_none = os.path.join(d, 'no_such.db')
        rid = list(range(1, 1001))
        rid_demo = [2, 4, 6, 8]
        rid_absent = list(range(1001, 2001))

        def arm(name, expect_ok, fn):
            try:
                got = fn()
                ok = bool(got.get('ok'))
                reason = got.get('reason')
                measured = got.get('measured')
            except GateTableEmpty as exc:
                ok, reason, measured = False, 'table_empty', None
                got = {'detail': str(exc)}
            except GateMeasureError as exc:
                ok, reason, measured = False, 'measure_error', None
                got = {'detail': str(exc)}
            arms.append({'arm': name, 'ok': ok, 'reason': reason, 'measured': measured,
                         'expect_ok': expect_ok, 'pass': ok == expect_ok})

        arm('P_embed_ok_900_of_1000', True,
            lambda: check(rc=0, todo_n=1000, measured=count_present(db_ok, rid)))
        arm('N_zero_embedded', False,
            lambda: check(rc=0, todo_n=1000, measured=count_present(db_sparse, rid_absent)))
        arm('N_rc_nonzero', False, lambda: check(rc=1, todo_n=1000, measured=900))
        arm('N_measure_error_missing_db', False,
            lambda: check(rc=0, todo_n=1000, measured=count_present(db_none, rid)))
        arm('N_below_min_ratio_400', False,
            lambda: check(rc=0, todo_n=1000, measured=400))
        arm('N_regression', False,
            lambda: check(rc=0, todo_n=1000, measured=900, before_n=100, after_n=99))
        arm('N_zero_delta', False,
            lambda: check(rc=0, todo_n=1000, measured=900, before_n=100, after_n=100))
        arm('P_empty_todo', True, lambda: check(rc=0, todo_n=0, measured=0))
        arm('P_allow_empty_explicit', True,
            lambda: check(rc=0, todo_n=1000, measured=0, allow_empty=True))
        # 反对① · 本机可独立复现：普通表（stdlib 造、无 vec0）也能跑通
        arm('P_demo_shadow_local_no_vec0', True,
            lambda: check(rc=0, todo_n=len(rid_demo), measured=count_present(db_demo, rid_demo)))
        # 反对③ · 表存在但全空 ≠ 表不存在 ≠ 探针死了（三个不同的 0）
        arm('N_table_empty_existing_but_empty', False,
            lambda: check(rc=0, todo_n=1000, measured=count_present(db_zero, rid)))
        # 闸 8 · 增量不足（非零增量，也不是回退）
        arm('N_insufficient_increment', False,
            lambda: check(rc=0, todo_n=1000, measured=900, before_n=0, after_n=100,
                          expected_n=1000))
        # 闸 8 向后兼容 · expected_n 缺省时完全不判
        arm('P_expected_n_absent_no_judge', True,
            lambda: check(rc=0, todo_n=1000, measured=900, before_n=0, after_n=100))
        # 断点重跑 · expected_n 显式 == 0（本轮应做 0 条）且增量为 0 ⇒ PASS
        #   （修「重跑被 zero_delta 假 FAIL」；measured=1000 表示段内 1000 条早已在库里）
        arm('P_no_op_already_complete', True,
            lambda: check(rc=0, todo_n=1000, measured=1000, before_n=1000, after_n=1000,
                          expected_n=0))
        # 负控 · 同一 expected_n=0 下真回退（after < before）仍必须 FAIL regression
        #   ⇒ 声明「本轮应做 0 条」不能成为吞掉向量减少的后门
        arm('N_no_op_not_masking_regression', False,
            lambda: check(rc=0, todo_n=1000, measured=1000, before_n=1000, after_n=999,
                          expected_n=0))
        # 原因粒度 · 真零嵌入（measured=0）即便增量也为 0，必须报 zero_embedded 而非
        #   zero_delta —— 否则接线后 seg8 事故签名被「零增量」掩盖（当日实测：旧序报 zero_delta）
        arm('N_zero_embedded_beats_zero_delta', False,
            lambda: check(rc=0, todo_n=1000, measured=0, before_n=0, after_n=0))
    return {'gate_version': GATE_VERSION, 'arms': arms,
            'all_pass': all(a['pass'] for a in arms)}


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return
    keys = ('gate_version', 'ok', 'reason', 'todo_n', 'measured',
            'required_min', 'share', 'failed', 'segments_checked')
    print(' '.join('%s=%s' % (k, obj[k]) for k in keys if k in obj))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='action_gate', description='动作层闸（P0②）')
    ap.add_argument('mode', choices=['measure', 'inline', 'audit', 'selftest'])
    ap.add_argument('--db')
    ap.add_argument('--table', default=DEFAULT_TABLE)
    ap.add_argument('--rowids-file')
    ap.add_argument('--segments-file')
    ap.add_argument('--full-list')
    ap.add_argument('--seg-size', type=int, default=1000)
    ap.add_argument('--rc', type=int, default=0)
    ap.add_argument('--todo-n', type=int, default=None)
    ap.add_argument('--measured', type=int, default=None)
    ap.add_argument('--before-n', type=int, default=None)
    ap.add_argument('--after-n', type=int, default=None)
    ap.add_argument('--expected-n', type=int, default=None,
                    help='闸8（可选）：本轮**应增量**。给了才判 —— '
                         '实际增量 < ceil(expected_n×min_ratio) ⇒ FAIL insufficient_increment；'
                         'expected_n=0 且增量=0 ⇒ PASS no_op_already_complete（断点重跑）；'
                         '不给 ⇒ 完全不判（向后兼容）')
    ap.add_argument('--min-ratio', type=float, default=DEFAULT_MIN_RATIO)
    ap.add_argument('--allow-empty', action='store_true')
    ap.add_argument('--only-segments', default=None,
                    help='逗号分隔的段号（1-based）：显式指定要判的段，忽略账本 completed 过滤')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)

    if a.mode == 'selftest':
        rep = selftest()
        _emit(rep, a.json)
        if not a.json:
            for x in rep['arms']:
                print('  %-30s ok=%-5s reason=%-24s measured=%-6s pass=%s'
                      % (x['arm'], x['ok'], x['reason'], x['measured'], x['pass']))
        return 0 if rep['all_pass'] else 1

    if a.mode == 'measure':
        if not a.db or not a.rowids_file:
            print('measure 需要 --db 与 --rowids-file', file=sys.stderr)
            return 2
        try:
            rep = measure_file(a.db, a.rowids_file, a.table)
        except GateMeasureError as exc:
            print(json.dumps({'ok': False, 'reason': 'measure_error',
                              'detail': str(exc)}, ensure_ascii=False))
            return 2
        _emit(rep, a.json)
        return 0

    if a.mode == 'inline':
        if a.todo_n is None:
            print('inline 需要 --todo-n（本段待做条数）', file=sys.stderr)
            return 2
        rep = check(rc=a.rc, todo_n=a.todo_n, measured=a.measured,
                    before_n=a.before_n, after_n=a.after_n,
                    expected_n=a.expected_n,
                    min_ratio=a.min_ratio, allow_empty=a.allow_empty)
        _emit(rep, a.json)
        return 0 if rep['ok'] else 1

    # audit
    if not (a.db and a.segments_file and a.full_list):
        print('audit 需要 --db / --segments-file / --full-list', file=sys.stderr)
        return 2
    try:
        only = ([int(x) for x in a.only_segments.split(',') if x.strip()]
                if a.only_segments else None)
        rep = audit_from_files(a.db, a.segments_file, a.full_list, seg_size=a.seg_size,
                               table=a.table, min_ratio=a.min_ratio,
                               allow_empty=a.allow_empty, only=only)
    except Exception as exc:
        print(json.dumps({'ok': False, 'reason': 'audit_error', 'detail': str(exc)},
                         ensure_ascii=False))
        return 2
    _emit(rep, a.json)
    if a.json:
        return 0 if rep['ok'] else 1
    for r in rep['rows']:
        print('  seg%-3s todo=%-5s embedded=%-5s share=%-7s ok=%-5s reason=%s'
              % (r['segment'], r['todo_n'], r['measured'], r['share'], r['ok'], r['reason']))
    return 0 if rep['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
