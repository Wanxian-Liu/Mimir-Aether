#!/usr/bin/env python3
"""
MimirAether TTY交互界面

增强的命令行交互，支持：
- readline历史
- 自动补全
- 流式输出
- 中断检测
"""

import os
import sys
import signal
import threading
from typing import Optional, Callable

# =============================================================================
# 简单的readline历史支持
# =============================================================================

class HistoryManager:
    """简单的历史管理"""
    
    def __init__(self, history_file: Optional[str] = None):
        self.history_file = history_file or os.path.expanduser("~/.mimiraether_history")
        self.history = []
        self._load_history()
    
    def _load_history(self):
        """加载历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = [line.rstrip('\n') for line in f if line.strip()]
            except Exception:
                self.history = []
    
    def _save_history(self):
        """保存历史"""
        try:
            with open(self.history_file, 'w') as f:
                for line in self.history[-1000:]:  # 最多1000条
                    f.write(line + '\n')
        except Exception:
            pass
    
    def add(self, line: str):
        """添加历史"""
        if line and line != self.history[-1] if self.history else False:
            self.history.append(line)
            self._save_history()
    
    def get_history(self):
        """获取历史"""
        return self.history
    
    def search(self, prefix: str):
        """搜索历史"""
        return [h for h in self.history if h.startswith(prefix)]


# =============================================================================
# ChatInterface
# =============================================================================

class ChatInterface:
    """
    TTY聊天界面
    
    功能：
    - readline历史
    - 流式输出显示
    - 简单的打断支持
    """
    
    def __init__(self, agent=None):
        self.agent = agent
        self.history_manager = HistoryManager()
        self._input_mode = 'simple'  # 'simple' or 'readline'
        
        # 尝试启用readline
        try:
            import readline
            self._input_mode = 'readline'
            self._setup_readline()
        except ImportError:
            pass
    
    def _setup_readline(self):
        """设置readline"""
        try:
            import readline
            
            # 设置历史
            for line in self.history_manager.get_history()[-50:]:
                readline.add_history(line)
            
            # 设置补全（可选）
            # readline.set_completer(completer)
        except Exception:
            pass
    
    def input(self, prompt: str = "你: ") -> str:
        """获取用户输入"""
        try:
            if self._input_mode == 'readline':
                import readline
                line = input(prompt)
                if line.strip():
                    self.history_manager.add(line)
                    readline.add_history(line)
                return line
            else:
                return input(prompt)
        except EOFError:
            return ""
        except KeyboardInterrupt:
            return ""
    
    def print_response(self, text: str):
        """打印响应"""
        print(f"\n🤖 MimirAether: {text}\n")
    
    def print_stream(self, text: str, end: str = ""):
        """流式打印"""
        print(text, end=end, flush=True)
    
    def print_error(self, text: str):
        """打印错误"""
        print(f"\n❌ 错误: {text}\n", file=sys.stderr)
    
    def print_info(self, text: str):
        """打印信息"""
        print(f"\nℹ️ {text}\n")
    
    def confirm(self, prompt: str) -> bool:
        """确认提示"""
        try:
            reply = input(f"{prompt} (y/n): ").strip().lower()
            return reply in ('y', 'yes', '')
        except (EOFError, KeyboardInterrupt):
            return False


# =============================================================================
# 带中断的输入监控
# =============================================================================

class InputMonitor:
    """监控用户输入，支持打断"""
    
    def __init__(self):
        self._interrupted = False
        self._input_buffer = []
        self._monitoring = False
        self._monitor_thread = None
    
    def start(self):
        """开始监控"""
        self._interrupted = False
        self._monitoring = True
        
        def monitor():
            while self._monitoring:
                try:
                    import select
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        char = sys.stdin.read(1)
                        if char:
                            self._input_buffer.append(char)
                            if char in ('\x03', '\x04'):  # Ctrl+C, Ctrl+D
                                self._interrupted = True
                except:
                    pass
        
        import threading
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
    
    def stop(self):
        """停止监控"""
        self._monitoring = False
    
    @property
    def interrupted(self) -> bool:
        """是否被打断"""
        return self._interrupted
    
    def clear(self):
        """清除打断标志"""
        self._interrupted = False
        self._input_buffer.clear()


# =============================================================================
# 简单的补全器
# =============================================================================

def basic_completer(text: str, state: int) -> Optional[str]:
    """简单的补全函数"""
    commands = [
        'status', 'config', 'doctor', 'setup', 'model',
        'cron', 'version', 'gateway', 'logs', 'help', 'quit', 'exit'
    ]
    
    options = [cmd for cmd in commands if cmd.startswith(text)]
    
    if state < len(options):
        return options[state]
    return None


if __name__ == "__main__":
    # 简单测试
    interface = ChatInterface()
    
    print("MimirAether TTY界面测试")
    print("输入 'quit' 退出\n")
    
    while True:
        try:
            user_input = interface.input("你: ")
            
            if not user_input:
                continue
            
            if user_input.lower() in ('quit', 'exit', 'q'):
                print("再见!")
                break
            
            # 模拟响应
            interface.print_response(f"收到: {user_input}")
            
        except KeyboardInterrupt:
            print("\n再见!")
            break
