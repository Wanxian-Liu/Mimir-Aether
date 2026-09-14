---
name: mimiraether-probe-attestation
description: RS17 探针自证闸——凡声明类结论（未生效/为 0/缺失/从未/not found）落盘前必须附「控制组通过的探针自证」。触发词：探针/自证/UNVERIFIED/误报/为 0/未生效/缺失/验证失败/负结论/grep 计数。是「探针失效被读成事实」这一类误报的机制化修复（非意志）。
---

# 探针自证闸（Probe Attestation Gate · RS17）

## 什么时候用（触发）

**只要你要说出一句"否定/缺失"的结论**，就先用它：

- 「X **未生效** / **未装载** / **没跑**」
- 「Y **为 0** / **0 次** / **从未**发生」
- 「Z **缺失** / **不存在** / **not found** / **查无**」
- 任何 `grep -c` / `awk` / `ls` / 计数类探针的**输出即结论**的场合

**不适用**：正向结论（"已生效/有 3 条"）不必自证；但若正向结论也靠脚本计数，同样建议自证。

## 为什么必须机制化（不要靠记性）

实证：2026-09-12 我命名了「探针未验证就下结论」，随后**两天重犯 14 次**。历史误报：
- 未转义 `[COMPRESS-RESULT]` 当正则（真行名是 `[COMPRESS] result`）→ 假计数 0
- `awk '$2>="13:53:54"'` 按**字典序**比时刻 → 跨天误计
- `ls` 空输出被读成"文件不存在"（`~` 展开问题）

共同结构：**探针失效 → 输出被当成事实**。命名失败 ≠ 修好失败。

## 怎么用（三步）

```bash
cd ~/src/MimirAether
./.venv/bin/python -m agent.probe_attest \
  --claim '<你要说的结论>' \
  --probe 'grep -c "PATTERN" {INPUT}' \
  --positive <已知为真的样本> \
  --negative <已知为假的样本> \
  --target  <真实样本>
# exit 0 = VERIFIED（可当事实用）
# exit 3 = UNVERIFIED（不许当事实用，只能标 UNVERIFIED）
```

**控制组语义**（这是全部价值所在）：

| 组 | 输入 | 期望 | 含义 |
|:--|:--|:--|:--|
| positive | **已知为真**的样本 | `seen` | 探针能看到"有" |
| negative | **已知为假**的样本 | `none` | 探针能看到"没有" |
| target | 真实样本 | —— | 只有前两组都合格，这行才可信 |

- **正控失败** = 探针在已知有货的样本上都报空 ⇒ 探针坏了（**与真实样本说什么无关**）
- **负控失败** = 恒真探针（如 `echo 1`）
- 三类结构性无效：无 `{INPUT}` 占位符 / 正负控样本相同 / 空探针

## 关键陷阱（都是实测踩过的）

1. **控制样本必须自己先验证**。我曾拿"真实文件第一行"当已知为真样本——那行其实是 rollback 行，正控当场失败。**控制样本本身也是一个未验证假设**，先 `grep -c` 自检（应为 1 / 0）再用。
2. **格式要对齐**。真实台账是 `{"outcome": "applied"}`（带空格），我手写的紧凑 JSON `{"outcome":"applied"}` 不匹配 → 正控失败。**用 `grep -m1` 从真实数据里摘样本**，别手写。
3. **`grep -c` 返回单个 `0` 视为 `none`**（见 `observe()` 口径）；多行输出为 `seen`。
4. **不要为了过关把探针放宽**——那正是"闸门越调越松"的老病（同 Loki Q1）。先判探针是否有效，再判结论。
5. `--list N` 读台账；台账是 **append-only JSONL**，四方可审计。

## 闸门行为（守着我，不靠我记）

- 挂在 `agent/verify_before_report_guard.py::should_block_finish()`，**在**"调过工具就放行"那条旧判据**之前**（否则永远够不着——探针本来就要调工具）
- 命中声明类结论 + 本轮无自证 ⇒ **拦一次**，注入 `[BLOCKED:probe-attest]` 专用提示（含 CLI 用法）
- 反死锁：同轮已有该标记 ⇒ 不再拦（放行但**自动落一条 UNVERIFIED**）
- 台账：`~/.mimiraether/data/ops/probe_attest.jsonl`

| env | 默认 | 作用 |
|:--|:--|:--|
| `MIMIR_PROBE_ATTEST` | `1` | 总开关 |
| `MIMIR_PROBE_ATTEST_MODE` | `nudge` | `off` / `nudge`（拦一次） / `hard`（每次都拦） |
| `MIMIR_PROBE_ATTEST_TTL` | `900` | 自证有效窗口（秒） |

**回滚**：`MIMIR_PROBE_ATTEST=0`（秒级，无需回退代码）。

## 取证纪律

- 自证成功的记录要**贴在报告里**（`verdict` + 两个控制组的 observed + target）
- 自证失败时，**先怀疑探针，再怀疑结论**——绝大多数时候是探针
- 探针自纠要**写进当日 notes**：失败模式 + 对策（否则下次重犯）

## 相关文件

- 模块：`agent/probe_attest.py`
- 测试：`tests/agent/test_probe_attest.py`（27 例，含 09-13 误报回归；已登记 Gate2）
- 设计文档（两方案对比与合并）：`~/.mimiraether/notes/2026-09-14-RS17-probe-attestation-two-plans.md`
