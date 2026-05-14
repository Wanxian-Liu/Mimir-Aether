#!/usr/bin/env bash
# Task 3 环境准备: 创建错误场景
set -e
WORKDIR="${1:-/tmp/benchmark-sandbox}"
ERRDIR="$WORKDIR/errrec"
mkdir -p "$ERRDIR"

# A: 损坏的 JSON（少一个引号）
cat > "$ERRDIR/broken.json" << 'EOF'
{
  "name": "test,
  "version": "1.0"
}
EOF

# B: 只读文件
echo "original content - do not overwrite" > "$ERRDIR/readonly.txt"
chmod 444 "$ERRDIR/readonly.txt"

# C: 目录伪装文件
mkdir -p "$ERRDIR/data_dir"
echo "this is a file inside a dir" > "$ERRDIR/data_dir/note.txt"

echo "✅ errrec 错误场景就绪"
