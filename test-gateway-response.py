#!/usr/bin/env python3
"""测试Mimir gateway是否正常响应（走api_server）"""
import json, urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:18999/v1/chat/completions",
    data=json.dumps({
        "model": "MimirAether",
        "messages": [{"role": "user", "content": "回复：OK"}],
        "max_tokens": 30,
    }).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print(f"状态: {resp.status}")
    print(resp.read().decode()[:300])
except Exception as e:
    print(f"失败: {e}")
