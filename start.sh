#!/bin/bash
# 体育新闻聚合工具 - 一键启动脚本
# 用法: 在终端执行  bash start.sh   然后浏览器打开 http://localhost:8501
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PY="/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python"

echo "▶ 检查依赖..."
if ! "$PY" -c "import streamlit" >/dev/null 2>&1; then
  echo "✗ 缺少 streamlit，正在安装..."
  "$PY" -m pip install --progress-bar off streamlit
fi

echo "▶ 启动 Streamlit (http://localhost:8501) ..."
# 先关掉可能残留的旧进程
pkill -f "streamlit run app.py" 2>/dev/null || true
sleep 1
"$PY" -m streamlit run app.py --server.port 8501 --server.headless true --server.address 127.0.0.1
