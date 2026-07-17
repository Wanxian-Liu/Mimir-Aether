# MimirAether 蒸馏执行技能

## 目的
确保蒸馏操作（`sync_run_dream_cycle()`）在正确的路径上执行，可写成可验证的结果，
避免"我以为做了但盘上没变"的循环。

## 根因记录（2026-07-15 最终闭环）

### 真正的代码级根因

#### 第一层根因：persistent_store 内存缓存覆盖（哨兵机制修复）

`sync_run_dream_cycle()` 的 `_save_persistent()` 写入 20 kd 到 main 文件是正常的。但 `CrossSessionMemory.save()`（由 `persistent_store.py` 驱动）在每次保存时：

```
1. json.load(main) -> 读当前 main（此时是 20 kd）-> 备份到 .bak
2. 从内存缓存加载旧数据（59 kd）-> 写回 main -> 覆写为 59 kd
```

**所以 .bak 里一直有正确的 20 kd（蒸馏输出），但 main 总是被内存缓存覆盖回去。**

**修复：** 哨兵文件机制（commit `4912d77`）

1. `dream_memory.py` 的 `_save_persistent()` 写入 main + 写入 `.distilled` 哨兵文件
2. `cross_session_memory.py` 的 `_post_distill_sync()` 在 `save_persistent_merged()` 前检测哨兵 + 从磁盘重载缓存 + 清哨兵
3. 后续 `CrossSessionMemory.save()` 用重载过的 20 kd 而非旧 59 kd

#### 为什么之前 3 层"修复"都没触及根因

| 轮次 | 修复了什么 | 为什么没用 |
|:----|:----------|:----------|
| 第 1-6 轮 | API key 注入路径 / os.environ | dream_memory.py 代码始终正确，错在执行路径选择（execute_code 沙盒崩溃） |
| 第 7-8 轮 | `***` 字面量 / xxd 字节检查 | `***` 是 read_file 工具层密钥遮盖，代码字节始终是 `b"DEEPSEEK_API_KEY="` |
| 第 15-16 轮 | **哨兵机制 + 内存缓存同步** | **第一次触及真正的覆盖根因** |

#### 用户交互修正

用户在 `~/.mimiraether/config.yaml` 的 `provider_registry` 中加了凭据回退层。

#### 最终验证（2026-07-15 15:52 CST）

| 指标 | 蒸馏前 | 蒸馏后 | 验证 |
|:----|:-----:|:-----:|:----|
| key_decisions | 59 | **20** (100% tip+cc) |
| learned_patterns | 53 | **30** (100% tip) |
| behavioral_constraints | 5 | **5** |
| 哨兵文件 `.distilled` | — | 时间戳 2026-07-15T15:52:59 |
| 三法验证 | — | json.load + 文件大小 + 哨兵存在 |
| git commit | — | `4912d77` — 2 文件：dream_memory.py + cross_session_memory.py |

### 之前为什么一直说"成功了"但盘上没变

| 执行路径 | 结果 |
|:--------|:-----|
| **`execute_code` 沙盒** | asyncio 事件循环嵌套 -> RuntimeError |
| **`cronjob` AIAgent prompt** | AIAgent 编造报告，不执行真实函数 |
| **`terminal` 独立进程** | 唯一成功执行 `_save_persistent()` 的路径 |
| **Python 脚本用 `(ok, report)` 解包** | 函数返回 `-> str` 不是 `(bool, str)` |

### 关键告诫

#### JSON 路径陷阱

persistent.json 中 key_decisions/learned_patterns 在 `data["memory"][...]` 下，**不是** `data["key_decisions"]`。
之前 15+ 轮"验证未通过"的真正根因：查错了 JSON 嵌套路径。

错误：
```python
kd = data.get("key_decisions", [])  # 永远返回空列表
```

正确：
```python
mem = data.get("memory", {})
kd = mem.get("key_decisions", [])
```

#### `***` 是源码真实字符串（xxd 字节级确认），不是纯工具遮盖

**两个事实共存：**

1. **dream_memory.py L447/468 源码包含 `***` 字面量**
    xxd 偏移 0x4b90: `0x2a 0x2a 0x2a` = `***`。代码是 `startswith(b"DEEPSEEK_API_KEY=***\n")`，
    所以 `_inject_api_key_from_proc()` 永远无法匹配真实 key（`sk-11f...`）。

2. **蒸馏最终成功的真正修复是 provider_registry 回退**
    用户在 `~/.mimiraether/config.yaml` 的 `providers.deepseek` 层加了真实 key，
    绕过了 `_inject_api_key_from_proc()` 的 `***` 比较。蒸馏的哨兵机制修复（commit `4912d77`）
    解决了内存缓存覆盖问题，但 `***` 代码本身从未被修复——是 provider_registry 回退让蒸馏得到了 key。

**教训：** `README`/`cat`/`read_file` 确实会遮盖 key 内容，但 `***` 在源码中是真实的。
不要仅凭"工具会遮盖 key"的推理就断定代码没有 `***`——应以 xxd 原始字节为准。

### 执行路径铁律

- **terminal** — 唯一能成功抵达 `_save_persistent()` 的路径。独立进程无事件循环冲突。
- ~~`execute_code`（沙盒）~~ — 因 asyncio 事件循环嵌套冲突，永远崩溃于 RuntimeError。
- ~~`AIAgent cron prompt`~~ — AIAgent 会编造"成功报告"而非真实执行。
- ~~`dry_run=True`~~ — 不调 LLM，不写盘，返回空报告。

### 验证铁律

1. terminal 执行完成后，**必须紧跟 read_file 读回 persistent.json 确认数据变化**。
2. 不凭 terminal 输出文本中的"写入成功"字样汇报 — 读盘确认 kd <= 20 / lp <= 30 / bc <= 8 / 100% tip_type+cause_chain 后才开口。
3. 同一回合内先后调用 terminal（写盘）-> read_file（验证），不在同一段回复中先于 read_file 汇报"成功"。
4. **永不信任 terminal 输出中的"成功"二字** — `print("写入成功")` 和 `_save_persistent()` 真实被调用是两回事。必须用第二个工具（`read_file`/`execute_code`）读盘交叉验证。
5. **函数签名是 `-> str`，返回报告文本** — 不是 `(bool, str)`。不要试图 `ok, report = sync_run_dream_cycle()` 解包。

## 执行规则

### 第一条：只走 terminal 路径

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
# 期望值：kd <= 20, lp <= 30, bc <= 8
```

### 第三条：检查关键指标

| 检查项 | 期望 | 如果不符合 |
|:------|:----|:----------|
| key_decisions 条数 | <= 20 | 蒸馏未生效或函数报错 |
| learned_patterns 条数 | <= 30 | 同上 |
| tip_type 覆盖率 | 100% | LLM 调用可能失败（key 注入问题）|
| cause_chain 覆盖率 | 100% | 同上 |
| behavioral_constraints 条数 | 5-8 | 蒸馏逻辑未执行完 |

### 第四条：先失败再固化（Superpowers 原则）

在创建任何新技能/新规则之前，先观察真实失败：

1. 有没有在 `terminal` 之外（`execute_code` / `cronjob`）尝试蒸馏？-> 先不修代码，记录失败模式
2. 失败模式：asyncio 嵌套（沙盒）/ AIAgent 编报告（cron job prompt）
3. 确认了固定失败模式后，才创建约束

## 错误模式速查

| 症状 | 根因 | 解法 |
|:----|:----|:----:|
| `ValueError: too many values to unpack` | 用 `(ok, report)` 解包单返回值 | 用 `report = sync_run_dream_cycle()` |
| 输出"成功"但盘上不变 | 走错路径（execute_code 沙盒崩溃/ cron prompt 编造） | 检查 `jobs.json` 查看真正的 last_run |
| 报告生成但数据没变 | AIAgent 编造 | 走 terminal 路径重跑 |
| kd/lp 读回是 0 | 查了 `data["key_decisions"]` 而非 `data["memory"]["key_decisions"]` | 用 `data.get("memory", {}).get("key_decisions")` |
| main 是旧数据但 .bak 是新数据 | 内存缓存覆盖（persistent_store 写回旧数据）| 哨兵机制（已修复，commit 4912d77）|

## 版本历史

- 2026-07-12: 创建。基于 12 轮蒸馏执行失败 + 最终 terminal 路径成功。
- 2026-07-14: 追加 JSON 路径陷阱 + `***` 是工具层遮盖 + 错误模式表新增 JSON 路径错误行。
- 2026-07-15: **重写根因链** — 从"缩进错误"修正为真正的"内存缓存覆盖 + 哨兵机制修复"。追加三法验证方式。
