#!/usr/bin/env python3
"""验证api_server.py修复（v2）：语法+4处import"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import py_compile
py_compile.compile("gateway/platforms/api_server.py", doraise=True)
print("✅ 语法OK")

from mimir_constants import get_mimir_home
print("✅ mimir_constants.get_mimir_home ok")
from mimir_cli.profiles import get_active_profile_name
print("✅ mimir_cli.profiles ok")
from mimir_cli.tools_config import _get_platform_tools
print("✅ mimir_cli.tools_config ok")
from mimir_cli.auth import has_usable_secret
print("✅ mimir_cli.auth ok")

content = open("gateway/platforms/api_server.py").read()
assert "mimiraether_cli" not in content, "仍有mimiraether_cli残留！"
print("✅ api_server.py无mimiraether_cli残留")
