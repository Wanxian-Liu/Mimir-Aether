# Docker 标准化环境

FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    git curl jq \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install pytest --break-system-packages

# 工作目录
RUN mkdir -p /tmp/benchmark-sandbox
VOLUME /tmp/benchmark-sandbox

# 挂载基准任务和评分脚本
COPY benchmarks/ /app/benchmarks/

WORKDIR /app

# 入口: 准备环境后等待 Agent 接入
# Agent 需挂载自己的代码/配置
CMD ["/bin/bash"]
