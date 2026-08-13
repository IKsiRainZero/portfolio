#!/bin/bash
# Token Monitor — 启动桌面小部件监控 Claude Code token 消耗
# 需要先运行: cd token-monitor-main/token-monitor-main && npm install
# 用法: bash scripts/monitor_tokens.sh [widget|agent|once]

TM_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")/../token-monitor-main/token-monitor-main"

case "${1:-widget}" in
  widget) cd "$TM_DIR" && npm start ;;
  agent)  cd "$TM_DIR" && npm run agent ;;
  once)   cd "$TM_DIR" && npm run agent:once ;;
  *)      echo "用法: $0 {widget|agent|once}"; exit 1 ;;
esac
