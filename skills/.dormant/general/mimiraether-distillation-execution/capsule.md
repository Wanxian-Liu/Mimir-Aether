# [DORMANT] mimiraether-distillation-execution

**沉寂时间**: 2026-09-15T04:25:53.515665+00:00
**原始分类**: general
**描述**: 确保蒸馏操作（`sync_run_dream_cycle()`）在正确的路径上执行，可写成可验证的结果， 避免'我以为做了但盘上没变'的循环。 `sync_run_dream_cycle()` 的 `_save_persistent()` 写入 20 kd 到 main 文件是正常的。但 `CrossSessionMemory.save()`（由 `persistent_store.py` 驱动）
**触发阈值**: 60天未触碰

---

## 技能要点

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
之前 15+ 轮"验证未通过"的真正根因：查错

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-distillation-execution")` 即可自动唤醒。
