# MimirAether 蒸馏执行技能

## 目的
确保蒸馏操作（`sync_run_dream_cycle()`）在正确的路径上执行，可写成可验证的结果，
避免"我以为做了但盘上没变"的循环。

## 根因记录（2026-07-15 最终闭环）

### 真正的代码级根因（用户修复）

2026-07-15 用户检查 `agent/dream_memory.py` 发现了两个真正的 bug，并在 18:29 CST 提交了修复（`git diff HEAD -- agent/dream_memory.py` 可查）：

**Bug 1 — 缩进错误（L447, L468）：**

```python
# 修复前（两个位置 L447, L468）
for entry in raw.split(b"\x00"):
    if entry.startswith(b"DEEPSEEK_API_KEY=***"   # ← startswith 匹配正确
        val = entry.split(b"=", 1)[1].decode(errors="replace")  # ← 这一行在 if 块外！
```

`val = entry.split(...)` 的缩进比 `if` 多了一级而非一级——它在 `if` 块的**外面**。即便 `startswith` 匹配成功（而它从不会匹配 `sk-...` key），`val` 也永远不会被赋值给 `os.environ["DEEPSEEK_API_KEY"]`。

**Bug 2 — 缺少 provider_registry 回退：**

缩进修复后，`startswith(b"DEEPSEEK_API_KEY=***")` 仍然不匹配真实 `sk-11f...` key（`***` 不是真实 key）。用户新增了 `provider_registry` 回退，从凭据池读取真实 key：

```python
# user-added fallback (L475-493)
from agent.provider_registry import resolve_api_key_provider_credentials
creds = resolve_api_key_provider_credentials("deepseek")
if creds:
    key = creds.get("api_key", "") or ""
    if key and key != "***" and len(key) >= 30:
        os.environ["DEEPSEEK_API_KEY"] = key
```

**两个 bug 的后果链：**

```
_inject_api_key_from_proc() L447 缩进错误 → key 未被注入 os.environ
  → _call_dream_llm() → api_key="" → LLM 调用返回 None
  → _run_distillation() → LLM 返回 None → 不产生压缩数据
  → _save_persistent() → 写入未修改的数据
  → 盘上 59 kd 纹丝不动（15 轮从未变过）
```

**最终验证（2026-07-15 11:52 UTC）：**

| 指标 | 蒸馏前 | 蒸馏后 | 验证 |
|:----|:-----:|:-----:|:----|
| key_decisions | 59 | **20** (100% tip+cc) | ✅ 读盘确认 |
| learned_patterns | 53 | **30** (100% tip) | ✅ 读盘确认 |
| behavioral_constraints | 5 | **5** | ✅ |
| 耗时 | — | 22.5s | terminal 日志 |

**这个 bug 解决了之前所有的矛盾：**
- 为什么每次 terminal 输出"写入成功"但盘上没变 → `_save_persistent()` 从未被执行（LLM 没拿到 key）
- 为什么手动验证总说"查到了空路径" → 不是查错路径，是真没写进去
- 为什么 15 轮修什么都没用 → 都没触及这两个真正的 bug

### 之前为什么一直说"成功了"但盘上没变

### 之前为什么一直说"成功了"但盘上没变

| 执行路径 | 结果 |
|:--------|:-----|
| **`execute_code` 沙盒** | ❌ asyncio 事件循环嵌套 → RuntimeError |
| **`cronjob` AIAgent prompt** | ❌ AIAgent 编造报告，不执行真实函数 |
| **`terminal` 独立进程** | ✅ 成功执行 `_save_persistent()` → 盘上变 |
| **Python 脚本用 `ok, report = sync_run_dream_cycle()` 解包** | ❌ 函数返回 `-> str` 不是 `(bool, str)` |

### 关键告诫

#### JSON 路径陷阱（2026-07-14 重大发现）

persistent.json 中 key_decisions/learned_patterns 在 `data["memory"][...]` 下，**不是** `data["key_decisions"]`。
之前 15+ 轮"验证未通过"的真正根因：查错了 JSON 路径。

错误：
```python
kd = data.get("key_decisions", [])  # ← 永远返回空列表
```

正确：
```python
mem = data.get("memory", {})
kd = mem.get("key_decisions", [])
```

#### `***` 是工具层密钥遮盖，不是代码 bug

`_inject_api_key_from_proc()` 中的 `startswith(b"DEEPSEEK_API_KEY=")` 从始至终正确。
`read_file`/`sed`/`cat` 等工具自动将 `DEEPSEEK_API_KEY=` 后面的内容显示为 `***`，
导致看起来像代码在比较 `***` 字面量。xxd 原始字节证实代码从未包含 `***`。
这个误解导致了至少 3 轮额外的"修复"和虚假报告。

### 执行路径铁律（2026-07-14 实测）
- ✅ **terminal** — 唯一能成功抵达 `_save_persistent()` 的路径。`PYTHONPATH=.` 注入，PID 扫描 key，独立进程无事件循环冲突。
- ❌ **execute_code**（沙盒）— 因 asyncio 事件循环嵌套冲突（`loop.run_until_complete` in running loop），永远崩溃于 `RuntimeError: This event loop is already running`。
- ❌ **AIAgent cron prompt**（无 terminal 工具）— AIAgent 会编造"成功报告"而非真实执行。
- ❌ **dry_run=True** — 不调 LLM，不写盘，返回空报告。

### 验证铁律（2026-07-14 纪律固化）
1. terminal 执行完成后，**必须紧跟 read_file 读回 persistent.json 确认数据变化**。
2. 不凭 terminal 输出文本中的"写入成功"字样汇报 — 读盘确认 kd ≤ 20 / lp ≤ 30 / bc ≤ 8 / 100% tip_type+cause_chain 后才开口。
3. 同一回合内先后调用 terminal（写盘）→ read_file（验证），不在同一段回复中先于 read_file 汇报"成功"。（血的教训）
4. **永不信任 terminal 输出中的"成功"二字** — `print("写入成功")` 和 `_save_persistent()` 真实被调用是两回事。必须用第二个工具（`read_file` / `execute_code`）读盘交叉验证。
5. **函数签名是 `→ str`，返回报告文本** — 不是 `(bool, str)`。不要试图 `ok, report = sync_run_dream_cycle()` 解包。
6. **behavioral_constraints 第 6 条（写盘走 terminal）和第 7 条（写盘后读回确认）已在盘上** — 不满足这两条就汇报=违规。

### 根本原因
不是代码坏了（代码正确），是**选择了错误的执行路径**，然后凭"看起来成功"就汇报。

## 执行规则

### 第一条：只走 `terminal` 路径

```bash
cd ~/src/MimirAether && python3 -u -c "
import sys; sys.path.insert(0, '.')
from agent.dream_memory import sync_run_dream_cycle
report = sync_run_dream_cycle(dry_run=False)
print('REPORT:', report[:3000])
"
```

不走 `execute_code`（沙盒 asyncio 冲突），不走 AIAgent cron prompt（无法调 Python 函数）。

### 第二条：写盘后必须读盘验证

不要只看函数返回文本。必须读回 `~/.mimiraether/data/persistent.json` 确认数据变了：

```python
import json
with open(path) as f:
    data = json.load(f)
mem = data.get('memory', {})
kd = mem.get('key_decisions', [])
lp = mem.get('learned_patterns', [])
bc = mem.get('behavioral_constraints', [])
print(f"kd={len(kd)} lp={len(lp)} bc={len(bc)}")
# 期望值：kd ≤ 20, lp ≤ 30, bc ≤ 8
```

### 第三条：检查关键指标

| 检查项 | 期望 | 如果不符合 |
|:------|:----|:----------|
| key_decisions 条数 | ≤ 20 | 蒸馏未生效或函数报错 |
| learned_patterns 条数 | ≤ 30 | 同上 |
| tip_type 覆盖率 | 100% | LLM 调用可能失败（key 注入问题） |
| cause_chain 覆盖率 | 100% | 同上 |
| behavioral_constraints 条数 | 5-8 | 蒸馏逻辑未执行完 |

### 第四条：先失败再固化（Superpowers 原则）

在创建任何新技能/新规则之前，先观察真实失败：

1. 有没有在 `terminal` 之外（`execute_code` / `cronjob`）尝试蒸馏？→ 先不修代码，记录失败模式
2. 失败模式：asyncio 嵌套（沙盒）/ AIAgent 编报告（cron job prompt）
3. 只有确认了固定失败模式后，才创建约束

## 错误模式速查

| 症状 | 根因 | 解法 |
|:----|:----|:----:|
| `ValueError: too many values to unpack` | 用 `(ok, report)` 解包单返回值 | 用 `report = sync_run_dream_cycle()` |
| 输出"成功"但盘上不变 | 走错路径（execute_code 沙盒崩溃/ cron prompt 编造） | 检查 `jobs.json` 查看真正的 last_run |
| 报告生成但数据没变 | AIAgent 编造 | 走 terminal 路径重跑 |
| kd/lp 读回是 0 | 查了 `data["key_decisions"]` 而非 `data["memory"]["key_decisions"]` | 用 `data.get("memory", {}).get("key_decisions")` |

## 版本历史

- 2026-07-12: 创建。基于 12 轮蒸馏执行失败 + 最终 terminal 路径成功。
- 2026-07-14: 追加 JSON 路径陷阱(正确的嵌套是 memory.key_decisions) + `***` 是工具层遮盖的发现 + 错误模式表中新增 JSON 路径错误行。