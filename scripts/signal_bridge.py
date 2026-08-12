#!/usr/bin/env python3
"""
投递端修复（Backend Architect角色——Hermes落代码）
Mimir收尾三连的@hermes信号→写 ~/wiki/信号投递/ 目录（在ToolGuard base内——不用/tmp）
Hermes四方巡检cron检测该目录——信号可靠到达
"""
import os, json, datetime, sys, glob

SIGNAL_DIR = os.path.expanduser('~/wiki/信号投递/')

def ensure_dir():
    os.makedirs(SIGNAL_DIR, exist_ok=True)

def write_signal(agent, task, summary, commit=None, report=None):
    """Mimir收尾三连第3步：写@hermes信号（替代/tmp jsonl——ToolGuard友好）"""
    ensure_dir()
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
    """Hermes侧：读未处理的信号（processed=已处理文件名集合）"""
    ensure_dir()
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
