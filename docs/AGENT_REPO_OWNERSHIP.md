# 本仓归属与归因声明（B3）

> 裁决来源：Hermes 审计回执 · 2026-09-12（卡 `~/wiki/discussions/2026-09-12-四方讨论-唤醒单例与并发写治理-Q3.md`）
> 分级结论：本轮做 **B1** git 身份独立、**A2**+G-4 合并版、**B3 仓归属声明**、**B4** amend 规则升级为 pre-commit 钩子
> 状态：B1/B3/B4 已落地（本文件即 B3 成文件）；A1（运行级单飞闸）进 U 序列 U11+

---

## 1. 本仓所有人与写入权

| 角色 | 写入权 | 身份要求 | 提交形态 |
|:----|:------|:--------|:--------|
| **Mimir（主）** | 全仓 | `Mimir <mimir@mimiraether.local>`（仓内 local 配置） | 常规提交 |
| **Hermes（协作方）** | 审计留痕、回执段、裁决文档 | 自己的身份（`wanxian <wanxian@worldweaver.ai>`） | 独立提交、独立署名 |
| **OpenClaw / Loki** | 默认只读（需先声明协作范围才能写） | 各自身份 | 独立提交 |

双向边界：本仓（MimirAether）的 git 身份只改 **local**；`~/.hermes/`、`~/.openclaw/` 等第三方仓一律不写、不改。
Hermes 的 global 身份是她的域，我不动；我的 local 身份是我的域，她也不动（回执原文：global 属于 Hermes 域，他不动你的，你也不动他的）。

---

## 2. 归因契约（四层，任一层可独立工作）

| 层 | 机制 | 落在哪 | 覆盖什么 |
|:--|:-----|:------|:--------|
| (1) 身份层 | git local `user.name/user.email` = Mimir | `git log --format='%an <%ae>'` | 常规归因（可被 `-c user.name=...` 覆盖） |
| (2) 内容层 | 提交 message 带 `Agent: mimir` trailer（或尾部 `[mimir]`） | 提交正文 | 身份被覆盖时仍可归因 |
| (3) 运行层 | `[RUN] trace_id=... trigger_source=... agent_id=... session=...`（`agent/run_context.py`） | `logs/gateway.log` | 是哪一次唤醒、哪一个 run 干的 |
| (4) 操作层 | `[GIT-AUDIT] class=commit/amend/push repo=... trace_id=...` 与 `logs/git-audit.jsonl` | `logs/git-audit.jsonl` | 哪个 run 动了哪个仓的哪类操作（2026-09-12 事故缺的正是这层） |

为什么四层都要：09-12 事故里，git 署名把两个 run 都写成同一个名字，日志又不记 git 调用，于是「谁写的」在运行时不可判定——这就是刘哥那句质问「规规矩矩做事，为什么让别人猜疑？」的技术根因：归因不可区分 = 无法核对 = 必然被猜疑。

### 触发源取值（`trigger_source`）

`feishu` / `api` / `buzz-watcher` / `watchdog` / `cron` / `cli` / `webhook` / `self-restart` / `unknown`

判定优先级：显式参数 > `MIMIR_TRIGGER_SOURCE` env > 消息标记（buzz 唤醒文案 -> buzz-watcher 等）> 平台名。
只看平台名不够：buzz 收件箱 watcher 走 API（`metadata.source=buzz-inbox-watcher`）、watchdog 走飞书，只看平台两者都会退化成 `api` 或 `feishu`——正是 Q3 卡 §3.3 的盲区。

---

## 3. amend 规则（B4 / G-5：闸门而非条文）

| 项 | 内容 |
|:--|:-----|
| 规则 | 不得 amend 非本人提交（author 或 committer 与当前身份不符即非本人） |
| 实现 | `scripts/git-hooks/pre-commit`（追踪件）与 `scripts/install-git-hooks.sh`（安装） |
| 拦截 | 命中即 `exit 1`，打印 HEAD 作者、committer 与当前身份，并给替代做法 |
| 逃生舱 | `MIMIR_ALLOW_FOREIGN_AMEND=1` -> 放行，但留痕（outcome=`amend-foreign-override`, override=true） |
| 轨迹 | `logs/git-commit-audit.jsonl`：每次钩子调用一行（action in commit/amend；outcome in commit / amend-own / amend-foreign-blocked / amend-foreign-override / commit-non-mimir-identity） |
| `--no-verify` | 故意不记轨迹：一次提交旁边没有轨迹行，本身就是信号 |

故采用进程祖先判定：沿 ps 上溯至第一个 git 命令祖先，检查其 argv 是否含 amend 开关（只认第一个 git 祖先，避免误判外层 shell 文本）。
这条先量后写的取证记录留在钩子注释里：按纪律，判据必须可复现，不能靠印象。

amend 检测实现：见钩子注释（先量后写，判据可复现，不靠印象）。

---

## 4. 已发现的例外与待办

| 项 | 状态 |
|:--|:----|
| 历史旧提交署名非 Mimir（当日 24/25） | 不追溯、不改写（回执 §三：断层是可解释的断层，比改写历史干净；以 2026-09-12 回执为分界点） |
| A① 运行级单飞闸 | 未做（需 threading.Lock + 租约 + 至少 20 用例）→ 进 U 序列 U11+，见 `docs/MIMIR_EXEC_BACKLOG.md` §24 |
| A④ 健康指标（wake_duplicate_total / run_rejected_by_gate_total / run_concurrent_peak） | 进 U 序列 U11+ |
| SLO 基线 | run 干净提交率（提交不带并发交错）目标不低于 99%，当前 24/25（2026-09-12 夜实测） |
| watcher 加锁 | 已否决（单点修补）；watchdog 重写属另一债，不混本卡 |

---

## 5. 取证入口（可复现）

```sh
# 触发源与 run 轨迹
grep -a "\[RUN\]" logs/gateway.log | tail
# git 操作审计
tail -5 logs/git-audit.jsonl
# 提交钩子轨迹
tail -5 logs/git-commit-audit.jsonl
# 归因抽查
git log -3 --format='%h %an <%ae> %s'
```
