#!/bin/bash
# 启动开发服务器并启用 DEBUG 级别日志
# 用于诊断 DeepSeek Agent 循环停止问题

cd "$(dirname "$0")"
echo "Starting development server with DEBUG logging..."
echo "Press Ctrl+C to stop"
echo ""

uv run uvicorn app.main:app --reload --log-level debug --host 0.0.0.0 --port 8000
