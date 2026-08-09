#!/usr/bin/env python3
"""
Mimir Buzz 内容级处理循环 v2 —— 收到@消息 → LLM理解 → 完整回复频道

v2 修复：捕获 agent 的最终输出（run_task 返回码不是文本，改用
execution result / stdout 捕获），确保频道收到完整内容级回复。
"""
import os, sys, asyncio, json, subprocess, io, contextlib

# 注入真key
home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

INBOX = "/tmp/buzz-inbox-mimir.jsonl"
SEND_SCRIPT = os.path.join(os.path.dirname(__file__), "scripts", "buzz-mimir-send.js")
MIMIR_SK = "1d2298b4f2062bf7f8eef9b769f3486f9475481d915d7996eca89376eccc592e"
SEEN_FILE = "/tmp/buzz-content-seen-mimir.txt"  # 已处理消息去重（方案A）

def send_to_channel(content, mention_pub=None):
    env = dict(os.environ)
    env["BUZZ_SK"] = MIMIR_SK
    env["BUZZ_CHANNEL"] = "7eb862af-f5a5-4f1a-9cea-0fb20322eeb8"
    env["BUZZ_CONTENT"] = content
    env["BUZZ_MENTION"] = mention_pub or ""
    r = subprocess.run(["node", SEND_SCRIPT], env=env, capture_output=True, text=True, timeout=15)
    print(f"📤 发送: {r.stdout.strip()[:40]}")

async def main():
    # 方案A：已处理消息去重（seen文件）+ 过滤确认类消息
    seen = set()
    if os.path.exists(SEEN_FILE):
        seen = set(open(SEEN_FILE).read().splitlines())

    # 方案B：rate-limit（防高频触发，30秒内不重复跑）
    import time as _time
    RATE_FILE = "/tmp/buzz-content-rate-mimir.txt"
    if os.path.exists(RATE_FILE):
        try:
            last = float(open(RATE_FILE).read().strip())
            if _time.time() - last < 30:
                raise SystemExit(0)  # rate-limit：静默
        except:
            pass

    try:
        lines = open(INBOX).readlines()
        if not lines:
            print("收件箱为空")
            return

        # 修复v2：过滤从"全文词匹配"改为"开头类型标记匹配"（防任务消息含'回执'被误杀）
        # 只跳过明确标记为确认/待命类的消息（开头20字内判定）
        # 修复v3（2026-08-05）：加"【Openclaw】/【Loki】写入路径/待命/已落盘"——回执噪音漏过过滤的根因
        CONFIRM_PREFIX = ["【REPLY】", "【Mimir】", "【Loki 待命】", "【OpenClaw 待命】",
                          "✅ 已收", "✅ 收到", "已收", "收到。", "收到，", "停】",
                          "【REPLY", "【Mimir】收",
                          "【Openclaw】写入路径", "【Openclaw】立场", "【Openclaw】✅",
                          "【Loki】写入路径", "【Loki】【Loki 待命", "【Loki】**", "【Loki】✅",
                          "【OpenClaw琬弦→Hermes】"]
        target = None
        for line in reversed(lines):
            try:
                d = json.loads(line)
                mid = d.get("id", "")
                content = d.get("content", "") or ""
                # 跳过已处理
                if mid and mid in seen:
                    continue
                # 开头20字含确认标记 → 跳过（确认类）
                head = content[:20]
                if any(p in head for p in CONFIRM_PREFIX):
                    continue
                # 找到第一条真正的任务消息
                target = d
                break
            except:
                continue

        if target is None:
            # 没有真正的任务消息——静默（不打扰）
            raise SystemExit(0)

        latest = target
        content = latest.get("content", "")
        from_pub = latest.get("from", "")
        msg_id = latest.get("id", "")

        # 去重：已处理过的不再处理（静默——no_agent cron空stdout不投递）
        if msg_id and msg_id in seen:
            raise SystemExit(0)

        print(f"📩 处理: {content[:70]}")
    except Exception as e:
        print(f"读收件箱失败: {e}")
        return

    task = f"""你在Buzz频道收到Hermes发来的消息，来自 {from_pub}。
消息内容：{content}

第一步：判断消息类型——
- 若是【任务消息】（含"新任务""请写""写入""完成你的段""读X并输出到Y""待办""落盘""复盘""反思""研究""审计""评估"等）：执行完整任务，**该写文件就写文件**（用write_file/patch落盘到指定路径），该验证就验证（grep/stat），任务要求的落盘产出必须完成。
- 若是【讨论消息】（含"立场""同意""回执""待命"等，且**不含任务词**）：只需输出回复文本（50-200字，观点明确），不需要写文件。
- 若是【询问】消息：直接回答。
- 修复（2026-08-05）：**任务词优先**——消息含"待办/写入/落盘/输出到"等任务词时，即使也含"讨论"，也按【任务消息】处理（必须落盘）。

第二步：按消息类型执行——
- 任务消息：完成落盘后，输出简短回执（做了啥+验证结果+文件路径）
- 讨论/询问消息：直接输出回复正文，作为频道消息发出

⚠️ 铁律（修复v5.1，2026-08-05）：**任务消息无论调研多少步（读卡/查盘/搜历史），最后必须 write_file/patch 写出你的段**——调研≠完成，**没有落盘=任务未完成**。结束前自检：我写盘了吗？没有→立即写。

现在开始处理："""

    # 捕获agent输出
    from mimir_cli.task_runner import run_task
    buffer = io.StringIO()
    result = None
    try:
        with contextlib.redirect_stdout(buffer):
            result = await run_task(task=task, model="deepseek-v4-flash", max_iterations=12, verbose=True)
    except Exception as e:
        print(f"agent执行异常: {e}")
        buffer.write(f"\n[异常] {e}")

    # ===== C1产出门禁v7（2026-08-08 四方共识+刘哥确认）=====
    # 目标：治"调研死循环"（读了N个文件但没写盘就结束）
    # v7修复（对比v6）：
    #   1. 时区统一——轨迹目录按UTC命名（Mimir发现：本地08-08 vs UTC轨迹08-07——找不到"今天"→门禁失效）
    #   2. 目标文件新鲜度主判断——任务含"写入XX卡"→查目标卡mtime（不依赖轨迹——"写到目标"才算数）
    #   3. 轨迹检查降为辅助（不再作为唯一依据）
    # 保留：调研能力+自我进化能力（只治"忘了产出"）
    import glob as _glob
    import datetime as _dt
    traj_dir = os.path.expanduser("~/.mimiraether/data/trajectories")
    
    # === 1. 时区统一：找轨迹目录（UTC + 本地 双查兼容）===
    today_utc = _dt.datetime.utcnow().strftime("%Y-%m-%d")
    today_local = _time.strftime("%Y-%m-%d")
    latest_traj = None
    for td in [today_utc, today_local]:
        td_path = os.path.join(traj_dir, td)
        if os.path.isdir(td_path):
            trajs = sorted(_glob.glob(os.path.join(td_path, "*.jsonl")), key=os.path.getmtime)
            if trajs:
                # 取最新的（mtime）
                candidate = trajs[-1]
                if latest_traj is None or os.path.getmtime(candidate) > os.path.getmtime(latest_traj):
                    latest_traj = candidate
    
    # === 2. 目标文件新鲜度主判断 ===
    # 从任务内容提取目标卡路径
    import re as _re2
    import os.path as _osp2
    # v7.2修复（2026-08-08）：同时匹配 ~/ 和 /home/rayliu/ 两种路径（~开头的"~/wiki/..."之前没匹配到）
    # v7.3修复（2026-08-09 Hermes——Mimir假成功暴露）：任务里"参考/示范/例如"后面的路径是参考路径——不是目标
    #   ——正则提取会取错（Mimir取到 ~/.hermes/PROGRESS.md 参考——通过门禁——自己没建）
    #   ——修复：优先提取"你要建/你工作区/你的"附近的目标路径；参考路径（"参考/示范/例如/Hermes示范"后）排除
    target_paths = []
    # ① 优先：任务里"你(的)工作区/你要建/你的xxx"关联的路径（Mimir/Awaken后跟路径——任务自己的目标）
    _own_paths = _re2.findall(r"(?:你的工作区|你要建|你的[^\s，。]{0,6}|建在|写入)\s*[:：]?\s*(~/[^\s，。;；]+?\.md|/home/rayliu/[^\s，。;；]+?\.md)", content)
    for _tp in _own_paths:
        if _tp.startswith("~/"):
            _tp = _osp2.expanduser(_tp)
        if _tp not in target_paths:
            target_paths.append(_tp)
    # ② 补充：全部.md路径（但排除"参考/示范/例如/Hermes示范"后面的——那些是参考不是目标）
    _all_md = _re2.findall(r"(~/[^\s，。;；]+?\.md|/home/rayliu/[^\s，。;；]+?\.md)", content)
    for _tp in _all_md:
        # 排除参考路径：看它前面是否紧跟"参考/示范/例如/Hermes示范/示例"
        _before = content[max(0, content.find(_tp)-8):content.find(_tp)]
        if any(k in _before for k in ["参考", "示范", "例如", "示例", "样例", "比如"]):
            continue
        if _tp.startswith("~/"):
            _tp = _osp2.expanduser(_tp)
        if _tp not in target_paths:
            target_paths.append(_tp)
    # ③ 都没匹配到（无明确目标）——降级用轨迹（辅助判断）
    target_fresh = False
    target_hits = []
    if target_paths:
        for tp in target_paths:
            if os.path.exists(tp):
                mtime = os.path.getmtime(tp)
                if _time.time() - mtime < 600:  # 10分钟内被改
                    target_fresh = True
                    target_hits.append(tp)
    
    # === 3. 轨迹辅助检查（新鲜轨迹有无写盘）===
    # v7.1修复（2026-08-08）：has_write必须用结构化判断（tool_name字段）——裸子串"patch"会匹配session_start的系统提示
    traj_has_write = False
    if latest_traj:
        try:
            traj_mtime = os.path.getmtime(latest_traj)
            if _time.time() - traj_mtime <= 600:  # 10分钟内（新鲜）
                with open(latest_traj) as _tf:
                    _traj_lines = _tf.readlines()
                for _tl in _traj_lines:
                    if '"tool_name": "write_file"' in _tl or '"tool_name": "patch"' in _tl:
                        traj_has_write = True
                        break
        except Exception:
            pass
    
    # === 4. 判定：目标新鲜度(主) OR 轨迹有写盘(辅助) ===
    has_write_task = any(k in content for k in ["写", "写入", "追加", "落盘", "完成你的段", "输出到"])
    if has_write_task and target_paths:
        # 有明确目标路径——以目标文件新鲜度为准
        if target_fresh:
            print(f"✅ 产出门禁v7: 目标文件新鲜（{target_hits}）——写盘成功")
        elif traj_has_write:
            print(f"⚠ 产出门禁v7: 目标文件未新鲜，但轨迹有写盘（{latest_traj.split('/')[-1]}）——可能是写到别处，需人工确认")
        else:
            print(f"⚠ 产出门禁v7: 目标文件未新鲜+轨迹无写盘——调研未产出，补强制写盘")
            write_task = f"""你在Buzz频道收到消息（来自 {from_pub}）。
消息内容（需完成落盘）：{content}

你已经做完了调研，现在必须【写盘产出】：
1. 用 patch 追加到目标卡（任务指定的路径）
2. 写出你的段（五段式：【角色】【任务】【上下文】【分析】【结论】）
3. 写盘后输出回执含路径
不要继续调研！现在只做一件事：写盘。"""
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    await run_task(task=write_task, model="deepseek-v4-flash", max_iterations=8, verbose=True)
                print("✅ 产出门禁v7: 强制写盘任务已执行")
            except Exception as e:
                print(f"⚠ 产出门禁v7: 强制写盘失败 {e}")
    elif has_write_task and not target_paths:
        # 有写盘要求但无明确路径——以轨迹判断
        if traj_has_write:
            print(f"✅ 产出门禁v7: 轨迹有写盘（{latest_traj.split('/')[-1] if latest_traj else '?'}）")
        else:
            print(f"⚠ 产出门禁v7: 任务要求写盘但无目标路径+轨迹无写盘——需关注")
    else:
        print("产出门禁v7: 非写盘任务，跳过")


    output = buffer.getvalue()
    # 提取agent的最后一段回复（"【执行结果】"之后或最后的正文）
    reply_text = ""
    # 尝试从执行结果里提取
    if isinstance(result, str) and len(result) > 10:
        reply_text = result
    if not reply_text:
        # 从stdout提取：找最后的正文段落
        lines_out = [l.strip() for l in output.splitlines() if l.strip()]
        # 去掉框架行
        skip = {"=", "🎯", "任务", "模型", "最大", "【执行结果】", "✅", "SkillsQA", "Could not", "bash", "API call", "[Recovery]", "│", "─", "◇", "├", "╯", "╭"}
        candidates = [l for l in lines_out if not l.startswith(tuple(skip)) and len(l) > 10]
        if candidates:
            reply_text = candidates[-1]  # 最后一段正文
    if not reply_text or len(reply_text) < 10:
        # 修复（2026-08-05，刘哥指示"不补根因查"）：不再用假回执掩盖未落盘——真实检查产物
        has_write_task = any(k in content for k in ["写", "写入", "追加", "落盘", "完成你的段", "输出到"])
        if has_write_task:
            # 真实检查：该任务要求写盘，但agent没有产出——报真实状态，不撒谎"已落盘"
            reply_text = "⚠ Mimir未检测到落盘产物：任务要求写盘但agent回复中无写入路径/无产物确认。这本身是bug（读不写），正在排查。"
        else:
            reply_text = "已收到你的消息，Mimir正在处理。"

    print(f"📝 回复: {reply_text[:120]}")

    # Loki"任务后置审计"钩子：任务要求写盘时，验证产物是否真实落盘（完成=盘上有证据）
    has_write_task = any(k in content for k in ["写", "写入", "追加", "落盘", "完成你的段", "输出到"])
    if has_write_task:
        # 从任务里提取目标路径（"到X.md"/"X.md 末尾"）
        import re as _re
        path_matches = _re.findall(r"(/home/rayliu/\S+?\.md)", content)
        if path_matches:
            # 验证最近的目标文件mtime是否新鲜（5分钟内被修改）
            import subprocess as _sp
            fresh = []
            for p in path_matches:
                try:
                    r = _sp.run(["stat", "-c", "%Y", p], capture_output=True, text=True, timeout=5)
                    mtime = int(r.stdout.strip())
                    import time as _t2
                    if _t2.time() - mtime < 300:  # 5分钟内
                        fresh.append(p)
                except:
                    pass
            if fresh:
                print(f"✅ 落盘验证: {fresh}（mtime 5分钟内）")
            else:
                print(f"⚠ 落盘未验证: 目标 {path_matches} mtime 超5分钟——产物可能未写")

    reply = f"【Mimir】{reply_text[:400]}"
    send_to_channel(reply)

    # 方案A：标记已处理（防下次cron重复处理）
    if msg_id:
        seen.add(msg_id)
        with open(SEEN_FILE, "w") as f:
            f.write("\n".join(seen))

    # 方案B：记录rate-limit时间戳
    with open(RATE_FILE, "w") as f:
        f.write(str(_time.time()))

if __name__ == "__main__":
    asyncio.run(main())
