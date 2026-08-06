#!/usr/bin/env python3
"""Check python env + akshare availability in MimirAether venv."""
import sys, importlib.util
print("python:", sys.version.split()[0])
for m in ["pandas", "akshare", "requests"]:
    print(m, ":", importlib.util.find_spec(m) is not None)
