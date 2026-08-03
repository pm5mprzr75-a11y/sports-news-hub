#!/bin/bash
# 体育新闻聚合器 - 定时抓取包装脚本（供 launchd / cron 调用）
# 使用绝对路径，不依赖调用方的工作目录。
set -u
PY="/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python"
DIR="/Users/yoyo/WorkBuddy/2026-08-03-16-45-23/sports-news-hub"
LOG="$DIR/data/crawl.log"
mkdir -p "$DIR/data"
{
  echo "===== crawl start $(date '+%Y-%m-%d %H:%M:%S') ====="
  "$PY" "$DIR/scheduler/run_crawl.py" --days 7 >> "$LOG" 2>&1
  echo "===== crawl end   $(date '+%Y-%m-%d %H:%M:%S') exit=$? ====="
} >> "$LOG" 2>&1
