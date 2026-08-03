#!/bin/bash
# 体育新闻聚合工具 - Web 守护进程启动脚本（供 launchd 调用）
# launchd 会保持它常驻：崩溃自动重启、登录/开机自动启动。
# 手动运行也可：bash scheduler/run_web.sh
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
PY="/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python"
# exec 让 launchd 直接接管 python 进程（便于 KeepAlive 准确管理）
exec "$PY" -m streamlit run app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 127.0.0.1
