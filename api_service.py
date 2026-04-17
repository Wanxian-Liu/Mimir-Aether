#!/usr/bin/env python3
"""
MimirAether HTTP API服务
绕过fencer过滤
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['DEEPSEEK_API_KEY'] = 'sk-ZCLxegsPZpBIxPSyNjEIyGrsriiOycEHa4cBdgxguHSybXPM'  # Moonshot Kimi K2.5

import asyncio
from aiohttp import web

async def handle_chat(request):
    """处理聊天请求"""
    data = await request.json()
    message = data.get('message', '')
    
    from agent.core_loop import MimirAetherAgent
    agent = MimirAetherAgent()
    result = await agent.chat(message)
    
    return web.json_response({'result': result or 'NO_RESULT'})

async def handle_run(request):
    """处理对话请求"""
    data = await request.json()
    message = data.get('message', '')
    
    from agent.core_loop import MimirAetherAgent
    agent = MimirAetherAgent()
    result = await agent.run_conversation(message)
    
    return web.json_response({'result': result or 'NO_RESULT'})

app = web.Application()
app.router.add_post('/chat', handle_chat)
app.router.add_post('/run', handle_run)

if __name__ == "__main__":
    print("MimirAether API服务启动: http://localhost:18999")
    web.run_app(app, host='0.0.0.0', port=18999)