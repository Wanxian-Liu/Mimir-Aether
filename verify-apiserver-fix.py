#!/usr/bin/env python3
"""验证api_server.py修复：语法+import"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# 1. 语法检查
import py_compile
py_compile.compile("gateway/platforms/api_server.py", doraise=True)
print("✅ 语法OK")

# 2. import检查（4个模块）
from mimir_cli.config import get_mimir_home
print("✅ mimir_cli.config ok")
from mimir_cli.profiles import get_active_profile_name
print("✅ mimir_cli.profiles ok")
from mimir_cli.tools_config import _get_platform_tools
print("✅ mimir_cli.tools_config ok")
from mimir_cli.auth import has_usable_secret
print("✅ mimir_cli.auth ok")

# 3. 确认api_server.py里没有mimiraether_cli残留
content = open("gateway/platforms/api_server.py").read()
assert "mimiraether_cli" not in content, "仍有残留！"
print("✅ api_server.py无mimiraether_cli残留")
