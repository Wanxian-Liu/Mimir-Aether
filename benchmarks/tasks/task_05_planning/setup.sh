#!/usr/bin/env bash
# Task 5 环境准备: 创建 Hugo 迁移场景
set -e
WORKDIR="${1:-/tmp/benchmark-sandbox}"
PLANDIR="$WORKDIR/planning"
mkdir -p "$PLANDIR/docs" "$PLANDIR/output"

# 文章 1: 有 YAML frontmatter + 内部链接
cat > "$PLANDIR/docs/getting-started.md" << 'EOF'
---
title: "Getting Started"
author: "Mimir"
tags: ["intro", "guide"]
---

# Getting Started

Welcome to the project. See [configuration](docs/configuration.md) for setup.

## Prerequisites

- Python 3.10+
- Git
EOF

# 文章 2: 有 YAML frontmatter + 内部链接
cat > "$PLANDIR/docs/configuration.md" << 'EOF'
---
title: "Configuration Guide"
author: "Aether"
tags: ["config", "advanced"]
---

# Configuration Guide

After [getting started](docs/getting-started.md), configure your environment.

## Settings

Edit `config.yaml` with your preferences.
EOF

# 文章 3: 有 YAML frontmatter + 交叉引用
cat > "$PLANDIR/docs/api-reference.md" << 'EOF'
---
title: "API Reference"
author: "Mimir"
tags: ["api", "reference"]
---

# API Reference

See [configuration](docs/configuration.md) and [getting started](docs/getting-started.md).

## Endpoints

### GET /health
Returns server status.
EOF

echo "✅ planning 迁移场景就绪 (3 篇文章)"
ls -la "$PLANDIR/docs/"
