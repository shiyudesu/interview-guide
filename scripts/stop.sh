#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if [[ $# -gt 0 ]]; then
  echo "用法: ./scripts/stop.sh" >&2
  exit 2
fi

echo "正在停止 InterviewGuide 本地服务..."

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 Docker，本机没有可由此脚本停止的 Docker 服务。"
  exit 0
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "未找到 Docker Compose v2，无法识别项目服务。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 当前未运行，项目服务已经不可用，无需额外停止。"
  exit 0
fi

if ! docker compose down --remove-orphans; then
  echo "关闭失败，请运行 'docker compose ps -a' 和 'docker compose logs' 查看状态。" >&2
  exit 1
fi

echo
echo "本地服务已关闭。PostgreSQL、Redis、MinIO 和 Provider 密钥数据卷均已保留。"
echo "下次启动: ./scripts/start.sh"
