#!/usr/bin/env python3
"""
MimirAether HTTP API服务

OpenAI兼容的API端点，支持：
- POST /v1/chat/completions - 聊天补全（兼容OpenAI格式）
- GET /health - 健康检查
- POST /v1/runs - 启动任务运行

基于Hermes api_server.py设计，为MimirAether重新实现。
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import web

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入模型配置（动态读取OpenClaw配置）
from mimicore.config.model_defaults import get_model, get_available_models, DEFAULT_MODEL as MIMIR_DEFAULT_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# 常量配置
# =============================================================================

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 18999
MAX_STORED_RESPONSES = 100
MAX_REQUEST_BYTES = 1_000_000  # 1 MB
MAX_CONTENT_LENGTH = 65_536  # 64 KB

# =============================================================================
# 工具函数
# =============================================================================

def _normalize_chat_content(content: Any) -> str:
    """Normalize OpenAI chat message content into a plain text string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:MAX_CONTENT_LENGTH]
    if isinstance(content, list):
        parts = []
        for item in content[:1000]:  # 限制列表大小
            if isinstance(item, str):
                parts.append(item[:MAX_CONTENT_LENGTH])
            elif isinstance(item, dict):
                item_type = str(item.get("type", "")).strip().lower()
                if item_type in {"text", "input_text", "output_text"}:
                    text = item.get("text", "")
                    if text:
                        parts.append(str(text)[:MAX_CONTENT_LENGTH])
        return "\n".join(parts)[:MAX_CONTENT_LENGTH]
    try:
        return str(content)[:MAX_CONTENT_LENGTH]
    except Exception:
        return ""


def _create_error_response(error: str, code: int = 400) -> Dict:
    """创建错误响应"""
    return {
        "error": {
            "message": error,
            "type": "invalid_request_error",
            "code": code
        }
    }


# =============================================================================
# 全局Agent管理
# =============================================================================

class AgentManager:
    """
    管理Agent实例的类
    
    支持：
    - 单例模式（默认）
    - 会话隔离
    - 可选：通过 :meth:`set_llm_backend_override` 为**新建**的 Agent 注入 ``llm_backend``（测试/定制）
    """

    _instance: Optional['AgentManager'] = None
    #: 非 None 时，下一次创建的 ``MimirAetherAgent`` 会收到 ``llm_backend=``（通常仅测试使用）
    _llm_backend_override: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, Any] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    @classmethod
    def set_llm_backend_override(cls, backend: Optional[Any]) -> None:
        """为后续新创建的 API Agent 设置 ``LlmInvocationPort``；传 ``None`` 清除。"""
        cls._llm_backend_override = backend
    
    async def get_agent(self, session_id: Optional[str] = None) -> Any:
        """获取Agent实例"""
        if session_id is None:
            session_id = "default"
        
        async with self._lock:
            if session_id not in self._agents:
                from agent.core_loop import MimirAetherAgent
                kwargs = dict(
                    model=get_model(),
                    max_iterations=90,
                    platform="api",
                )
                if self.__class__._llm_backend_override is not None:
                    kwargs["llm_backend"] = self.__class__._llm_backend_override
                self._agents[session_id] = MimirAetherAgent(**kwargs)
                logger.info(f"创建新Agent实例: {session_id}")
            
            return self._agents[session_id]
    
    async def close_all(self):
        """关闭所有Agent"""
        async with self._lock:
            self._agents.clear()


# =============================================================================
# 请求处理器
# =============================================================================

async def handle_chat_completions(request: web.Request) -> web.Response:
    """
    处理 OpenAI 格式的聊天补全请求
    
    POST /v1/chat/completions
    
    请求体 (OpenAI格式):
    {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"}
        ],
        "stream": false,
        "max_tokens": 2048
    }
    """
    try:
        # 解析请求体
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                _create_error_response("Invalid JSON body"),
                status=400
            )
        
        # 获取参数
        model = body.get("model", get_model())
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        max_tokens = body.get("max_tokens", 4096)
        
        # 获取session_id
        session_id = request.headers.get("X-Session-ID", "default")
        
        # 规范化消息内容
        normalized_messages = []
        for msg in messages:
            normalized_msg = {
                "role": msg.get("role", "user"),
                "content": _normalize_chat_content(msg.get("content", ""))
            }
            normalized_messages.append(normalized_msg)
        
        logger.info(f"收到聊天请求: session={session_id}, model={model}, stream={stream}")
        
        # 获取Agent
        agent_manager = AgentManager()
        agent = await agent_manager.get_agent(session_id)
        
        if stream:
            # 流式响应
            return await _handle_stream_response(agent, normalized_messages, model, max_tokens)
        else:
            # 非流式响应
            return await _handle_non_stream_response(agent, normalized_messages, model, max_tokens)
            
    except Exception as e:
        logger.error(f"处理聊天请求失败: {e}")
        return web.json_response(
            _create_error_response(f"Internal error: {str(e)}", 500),
            status=500
        )


async def _handle_non_stream_response(agent: Any, messages: List[Dict], model: str, max_tokens: int) -> web.Response:
    """处理非流式响应"""
    try:
        # 从消息中提取最后一条用户消息
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            return web.json_response(
                _create_error_response("No user message found"),
                status=400
            )
        
        # 运行对话
        start_time = time.time()
        result = await agent.run_conversation(user_message)
        elapsed = time.time() - start_time
        
        # 构建响应
        response = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": str(result) if result else ""
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,  # 简化处理
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        logger.info(f"完成聊天请求: elapsed={elapsed:.2f}s")
        return web.json_response(response)
        
    except Exception as e:
        logger.error(f"处理非流式响应失败: {e}")
        return web.json_response(
            _create_error_response(f"Internal error: {str(e)}", 500),
            status=500
        )


async def _handle_stream_response(agent: Any, messages: List[Dict], model: str, max_tokens: int) -> web.Response:
    """处理流式响应"""
    
    async def generate():
        """生成SSE流"""
        try:
            # 从消息中提取最后一条用户消息
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                yield f"data: {json.dumps(_create_error_response('No user message found'))}\n\n"
                return
            
            # 创建流式回调
            full_content = []
            
            def stream_callback(text: str):
                full_content.append(text)
                # 发送增量
                chunk = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": text},
                            "finish_reason": None
                        }
                    ]
                }
                return f"data: {json.dumps(chunk)}\n\n"
            
            # 注册流式回调
            agent.stream_callback = stream_callback
            
            # 运行对话
            result = await agent.run_conversation(user_message)
            
            # 发送完成
            final_chunk = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"流式响应失败: {e}")
            yield f"data: {json.dumps(_create_error_response(str(e), 500))}\n\n"
    
    return web.Response(
        body=generate(),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


async def handle_health(request: web.Request) -> web.Response:
    """
    健康检查
    
    GET /health
    """
    return web.json_response({
        "status": "ok",
        "service": "MimirAether",
        "version": "0.1.0",
        "timestamp": int(time.time())
    })


async def handle_models(request: web.Request) -> web.Response:
    """
    列出可用模型
    
    GET /v1/models
    """
    models = [
        {
            "id": get_model(),
            "object": "model",
            "created": int(time.time()),
            "owned_by": "MimirAether",
            "note": "默认模型"
        },
        {
            "id": "deepseek/deepseek-chat",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "MimirAether"
        },
        {
            "id": "kimi-k2.5",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "Moonshot"
        }
    ]
    
    return web.json_response({
        "object": "list",
        "data": models
    })


async def handle_v1_runs(request: web.Request) -> web.Response:
    """
    启动任务运行
    
    POST /v1/runs
    
    返回202 Accepted和run_id
    """
    try:
        body = await request.json()
        task = body.get("task", "")
        model = body.get("model", get_model())
        
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"启动任务: run_id={run_id}, task={task[:50]}...")
        
        # 在后台运行任务
        asyncio.create_task(_run_task_background(run_id, task, model))
        
        return web.json_response({
            "run_id": run_id,
            "status": "pending",
            "task": task[:100]
        }, status=202)
        
    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        return web.json_response(
            _create_error_response(str(e), 500),
            status=500
        )


async def _run_task_background(run_id: str, task: str, model: str):
    """后台运行任务"""
    try:
        agent_manager = AgentManager()
        agent = await agent_manager.get_agent(f"run_{run_id}")
        result = await agent.run_conversation(task)
        logger.info(f"任务完成: run_id={run_id}, result={str(result)[:50]}...")
    except Exception as e:
        logger.error(f"后台任务失败: run_id={run_id}, error={e}")


# =============================================================================
# WebSocket支持（可选）
# =============================================================================

async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    """
    WebSocket连接
    
    WS /ws
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    session_id = request.headers.get("X-Session-ID", str(uuid.uuid4()))
    
    logger.info(f"WebSocket连接: session={session_id}")
    
    agent_manager = AgentManager()
    agent = await agent_manager.get_agent(session_id)
    
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message = data.get("message", "")
                    stream = data.get("stream", False)
                    
                    if stream:
                        # 流式处理
                        full_response = []
                        
                        def ws_stream_callback(text: str):
                            full_response.append(text)
                            # 发送增量到客户端
                            asyncio.get_event_loop().create_task(
                                ws.send_json({
                                    "type": "content_delta",
                                    "delta": text
                                })
                            )
                        
                        agent.stream_callback = ws_stream_callback
                        result = await agent.run_conversation(message)
                        
                        # 发送完成
                        await ws.send_json({
                            "type": "done",
                            "content": "".join(full_response)
                        })
                    else:
                        # 非流式
                        result = await agent.run_conversation(message)
                        await ws.send_json({
                            "type": "result",
                            "content": str(result) if result else ""
                        })
                        
                except json.JSONDecodeError:
                    await ws.send_json({"error": "Invalid JSON"})
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket错误: {ws.exception()}")
                
    finally:
        logger.info(f"WebSocket关闭: session={session_id}")
    
    return ws


# =============================================================================
# 主应用
# =============================================================================

def create_app() -> web.Application:
    """创建Web应用"""
    app = web.Application(
        client_max_size=MAX_REQUEST_BYTES
    )
    
    # 路由
    app.router.add_post('/v1/chat/completions', handle_chat_completions)
    app.router.add_get('/health', handle_health)
    app.router.add_get('/v1/models', handle_models)
    app.router.add_post('/v1/runs', handle_v1_runs)
    app.router.add_get('/ws', handle_websocket)
    app.router.add_post('/ws', handle_websocket)
    
    # 启动/关闭钩子
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    
    return app


async def _on_startup(app: web.Application):
    """应用启动"""
    logger.info("MimirAether API服务启动")
    logger.info(f"端点:")
    logger.info(f"  POST /v1/chat/completions - 聊天补全")
    logger.info(f"  GET  /health - 健康检查")
    logger.info(f"  GET  /v1/models - 模型列表")
    logger.info(f"  POST /v1/runs - 任务运行")
    logger.info(f"  WS   /ws - WebSocket")


async def _on_cleanup(app: web.Application):
    """应用关闭"""
    logger.info("关闭MimirAether API服务...")
    agent_manager = AgentManager()
    await agent_manager.close_all()
    logger.info("MimirAether API服务已关闭")


# =============================================================================
# 入口点
# =============================================================================

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MimirAether API服务")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--model", default=get_model(), help="默认模型")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 设置默认模型
    os.environ.setdefault("MIMIR_MODEL", args.model)
    
    app = create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           MimirAether API服务                               ║
║                                                              ║
║  HTTP: http://{args.host}:{args.port}                          ║
║  WebSocket: ws://{args.host}:{args.port}/ws                   ║
║                                                              ║
║  端点:                                                       ║
║    POST /v1/chat/completions - 聊天补全                      ║
║    GET  /health - 健康检查                                   ║
║    GET  /v1/models - 模型列表                               ║
║    POST /v1/runs - 任务运行                                 ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    web.run_app(
        app,
        host=args.host,
        port=args.port,
        access_log=logger if args.verbose else None
    )


if __name__ == "__main__":
    main()
