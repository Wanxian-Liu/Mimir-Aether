# P0② 动作层闸（2026-09-17）

## 为什么
Phase β 段8 的记账条件是 `rc == 0`（`build_phase_beta.py:107-108`）：
零嵌入也会 `rc=0` ⇒ 被记为完成 ⇒ 续跑按 `completed_segments` 选段 ⇒
该段 1000 条 rowid 永久跳过（其中 842 条本可嵌）。
W-β2 的 `consistent=False ⇒ NEED_HUMAN` 在**账本层**，checkpoint 早已落盘。
⇒ 账本层断言 ≠ 动作层闸门。

## 交付
1. `scripts/action_gate.py`（repo，版本控制）：**只看 DB 里有没有那些向量**。
   - 证据通道：vec0 虚表 `wiki_chunks_prefix` 读不了（无扩展），
     但其**影子表 `wiki_chunks_prefix_rowids` 是普通表**，stdlib sqlite3 直读。
   - `check()` 判定序（任一命中即 FAIL）：rc≠0 · 测量失败 · 回退 · 零增量 ·
     零嵌入 · 低于 `min_ratio`。空清单 = 显式 PASS（void ≠ 有货 ≠ 探针死了）。
2. `tests/scripts/test_action_gate.py`（21 例）：含 **fail-closed 三条**（测量失败/表缺失/库缺失）
   与**事故复现夹具**（7 段有货 + 1 段零货且记账 ⇒ 恰一段 FAIL）。
3. `beta_chain.py` 接线（home 侧，本目录留 pre-image + diff 以便追溯）：
   链在**账本对账通过之后、起下一段之前**再跑动作层闸；不通过 ⇒
   `STATE=NEED_HUMAN reason=action_gate_*` + 非 0 ⇒ 不续跑。
4. 生产审计输出（当前账本）：seg1..seg7 = 1.000/0.999/0.943/0.850/0.786/0.930/0.864 → PASS。
   事故时点回放（账本含段8）：seg8 `embedded=0` ⇒ `zero_embedded` ⇒ **rc=1**（拦截成立）。

## 未做（须他人执行，非我域）
- `build_phase_beta.py`（OpenClaw 域）**内联**调用：写 checkpoint 之前
  `python3 -m scripts.action_gate inline --rc $rc --todo-n $n --measured $measured || exit 1`。
  我未改他人文件 —— 片段已发四方裁决/落地。
- pc 全量（Hermes 域）：同族风险（18–22h CPU 跑完后无「真写进去了」的后置断言）。

## 回滚
```
cp scripts/migrations/20260917_p0b_action_gate/beta_chain.py.pre ~/.mimiraether/scripts/beta_chain.py
```
（`action_gate.py` 与测试为纯新增件，删文件即回滚。）
