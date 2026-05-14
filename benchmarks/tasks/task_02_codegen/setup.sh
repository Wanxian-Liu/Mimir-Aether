#!/usr/bin/env bash
# Task 2 环境准备: 创建有 bug 的初始代码
set -e
WORKDIR="${1:-/tmp/benchmark-sandbox}"
CODEDIR="$WORKDIR/codegen"
mkdir -p "$CODEDIR"

cat > "$CODEDIR/utils.py" << 'PYEOF'
def divide(a, b):
    return a / b

def safe_divide(a, b):
    if b == 0:
        return None
    return divide(a, b)
PYEOF

echo "✅ codegen 环境就绪"
