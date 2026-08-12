#!/usr/bin/env python3
"""
⚠️ ARCHIVED — 禁止 import/执行，仅留档（2026-08-13 Mimir P0-1收敛审计 B1修复）

历史：投递端修复（Backend Architect角色——Hermes落代码）
原用途：Mimir收尾三连的@hermes信号→写 ~/wiki/信号投递/ 目录
废弃原因：jsonl 活通道（signal-deliver.py → /tmp/buzz-inbox-hermes.jsonl）已接管；
~/wiki/信号投递/ 目录已移除（wiki gitignore 防污染）。
B1修复：删除 ensure_dir()——原 read_signals() 一调用就复活已移除的 wiki/信号投递/ 目录（假归档炸弹）。
"""
import os, json, datetime, sys, glob

SIGNAL_DIR = os.path.expanduser('~/wiki/信号投递/')

def write_signal(agent, task, summary, commit=None, report=None):
    """Mimir收尾三连第3步：写@hermes信号（已废弃——目录不存在时写入失败=防误用）"""
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'{ts}-{agent}-信号.json'
    signal = {
        'ts': datetime.datetime.now().isoformat(),
        'from': agent,
        'to': 'hermes',
        'type': 'completion',
        'task': task,
        'summary': summary,
        'commit': commit,
        'report': report,
    }
    path = os.path.join(SIGNAL_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(signal, f, ensure_ascii=False, indent=2)
    return path

def read_signals(processed=None):
    """Hermes侧：读未处理的信号（processed=已处理文件名集合）——目录不存在直接返回空（B1修复：不再复活目录）"""
    signals = []
    for f in sorted(glob.glob(os.path.join(SIGNAL_DIR, '*.json'))):
        name = os.path.basename(f)
        if processed and name in processed:
            continue
        try:
            with open(f, encoding='utf-8') as fh:
                signals.append(json.load(fh))
        except Exception:
            pass
    return signals

def mark_processed(signal_files):
    """Hermes侧：标记已处理（防重复——治Mimir审计的'无状态去重'漏洞）"""
    state = os.path.join(SIGNAL_DIR, '.processed')
    with open(state, 'a', encoding='utf-8') as f:
        for s in signal_files:
            f.write(s + '\n')

if __name__ == '__main__':
    # 测试：模拟Mimir发信号
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        path = write_signal('mimir', '投递端修复测试', '测试信号——验证投递链路')
        print(f'✅ 测试信号已写: {path}')
        sigs = read_signals()
        print(f'📩 读取到{len(sigs)}条信号')
        for s in sigs:
            print(f'  from={s["from"]} task={s["task"]}')
