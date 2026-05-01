#!/usr/bin/env python3
"""
Gateway Integration Example - 展示如何将Gateway与Agent连接

这是修复MimirAether消息触发机制的关键集成点。

问题：MimirAether的gateway有adapter/session/router结构，
      但没有实现"消息→agent→回复"的完整调用链。

解决方案：按照Hermes的模式，在gateway中添加集成层。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
MIMIR_AETHER_PATH = Path('/home/rayliu/.openclaw/projects/MimirAether')
sys.path.insert(0, str(MIMIR_AETHER_PATH))


class MimirAetherGateway:
    """
    Gateway集成类 - 桥接平台适配器和Agent
    
    学习自Hermes GatewayRunner._handle_message_with_agent()
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.sessions = {}  # session_id -> {history: [], context: {}}
    
    async def handle_message(self, message_text: str, session_id: str = None) -> str:
        """
        处理收到的消息并返回响应
        
        这是Hermes中 _handle_message_with_agent 的等价实现：
        1. 获取/创建session
        2. 获取history
        3. 调用agent.run_conversation(history=history)
        4. 更新history
        5. 返回响应
        """
        # 1. 获取或创建session
        if session_id is None:
            session_id = "default"
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "context": {}
            }
        
        session = self.sessions[session_id]
        history = session["history"]
        
        # 2. 调用agent，传入history
        result = await self.agent.run_conversation(
            user_message=message_text,
            conversation_history=history
        )
        
        # 3. 提取响应
        response = result.get("response", "")
        
        # 4. 更新history
        history.append({"role": "user", "content": message_text})
        history.append({"role": "assistant", "content": response})
        
        # 5. 保存更新后的history
        session["history"] = history
        
        return response
    
    async def handle_feishu_message(self, raw_event: dict) -> str:
        """
        处理飞书平台消息
        
        流程：
        1. 解析飞书事件 -> 提取文本和session
        2. 调用 handle_message
        3. 通过飞书API发送回复
        """
        # 解析飞书事件
        message_content = raw_event.get("event", {}).get("message", {}).get("content", {})
        if isinstance(message_content, str):
            import json
            message_content = json.loads(message_content)
        
        text = message_content.get("text", "")
        chat_id = raw_event.get("event", {}).get("chat_id", "")
        sender_id = raw_event.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "")
        
        # 使用sender_id作为session_key
        session_id = f"feishu_{sender_id}"
        
        # 处理消息
        response = await self.handle_message(text, session_id)
        
        return response


async def demo():
    """演示Gateway集成"""
    from agent.core_loop import MimirAetherAgent
    
    # 1. 初始化Agent
    agent = MimirAetherAgent(
        model="deepseek/deepseek-chat",
        max_iterations=10,
        platform="cli"
    )
    
    # 2. 创建Gateway
    gateway = MimirAetherGateway(agent)
    
    # 3. 模拟多轮对话
    print("=== Gateway Integration Demo ===\n")
    
    # 第一轮
    response1 = await gateway.handle_message("你好，我是负责人", session_id="user_1")
    print(f"User: 你好，我是负责人")
    print(f"Agent: {response1}\n")
    
    # 第二轮（带历史）
    response2 = await gateway.handle_message("还记得我叫什么吗？", session_id="user_1")
    print(f"User: 还记得我叫什么吗？")
    print(f"Agent: {response2}\n")
    
    # 检查历史
    print(f"=== Session History ===")
    history = gateway.sessions["user_1"]["history"]
    for i, msg in enumerate(history):
        print(f"{i+1}. [{msg['role']}]: {msg['content'][:50]}...")


if __name__ == "__main__":
    asyncio.run(demo())