#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if [[ $# -gt 0 ]]; then
  echo "用法: ./scripts/stop-http.sh" >&2
  exit 2
fi

echo "正在停止隔离的 HTTP 验收实例..."

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 Docker，本机没有可由此脚本停止的 HTTP 验收实例。"
  exit 0
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "未找到 Docker Compose v2，无法识别 HTTP 验收实例。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 当前未运行，HTTP 验收实例已经不可用，无需额外停止。"
  exit 0
fi

http_env_file=".env.http"
if [[ ! -f "$http_env_file" ]]; then
  http_env_file=".env.http.example"
fi

compose() {
  COMPOSE_PROFILES="" docker compose \
    --project-name interview-guide-http \
    --env-file "$http_env_file" \
    -f docker-compose.yml \
    "$@"
}

if ! compose down --remove-orphans; then
  echo "关闭失败，请检查 'docker compose --project-name interview-guide-http ps -a'。" >&2
  exit 1
fi

echo
echo "HTTP 验收实例已关闭，PostgreSQL、Redis、MinIO 和 Provider 密钥数据卷均已保留。"
echo "下次启动: ./scripts/start-http.sh"
