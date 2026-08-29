#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if [[ $# -gt 0 ]]; then
  echo "用法: ./scripts/stop-campus.sh" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 Docker，无需停止校园实例。"
  exit 0
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "未找到 Docker Compose v2，无法识别校园实例。" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 未运行，校园实例当前已不可用。"
  exit 0
fi
if [[ ! -f .env.campus ]]; then
  echo "未找到 .env.campus，无可识别的校园实例。"
  exit 0
fi

compose() {
  COMPOSE_PROFILES="" docker compose \
    --project-name interview-guide-campus \
    --env-file .env.campus \
    -f docker-compose.yml \
    "$@"
}

echo "正在停止 OpenTrek 校园比赛实例..."
compose down --remove-orphans

echo "校园实例已停止；PostgreSQL、Redis、MinIO 和 Provider 密钥数据卷均已保留。"
echo "下次启动: ./scripts/start-campus.sh"
