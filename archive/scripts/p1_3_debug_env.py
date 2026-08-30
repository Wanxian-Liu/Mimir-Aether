#!/usr/bin/env python3
"""Debug _load_env behavior in gateway-like env."""
import os, sys
sys.path.insert(0, "/home/rayliu/src/MimirAether")
print("HOME:", os.environ.get("HOME"))
from subagent_bridge import _load_env
env = _load_env()
print("DEEPSEEK in env:", "DEEPSEEK_API_KEY" in env)
print("key len:", len(env.get("DEEPSEEK_API_KEY", "")))
print("MIMIR_ENV exists:", os.path.isfile(os.path.expanduser("~/.mimiraether/.env")))
