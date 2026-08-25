#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

http_env_file=".env.http"
compose_project="interview-guide-http"

fail() {
  echo "错误: $*" >&2
  exit 1
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
    return
  fi
  od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
  printf '\n'
}

replace_generated_secret() {
  local name="$1"
  local value temporary_file
  if ! grep -Eq "^${name}=(GENERATE_ON_FIRST_START)?$" "$http_env_file"; then
    return
  fi
  value="$(random_secret)"
  temporary_file="$(mktemp)"
  awk \
    -v empty_target="${name}=" \
    -v legacy_target="${name}=GENERATE_ON_FIRST_START" \
    -v replacement="${name}=${value}" \
    '$0 == empty_target || $0 == legacy_target { print replacement; next } { print }' \
    "$http_env_file" >"$temporary_file"
  mv "$temporary_file" "$http_env_file"
}

ensure_http_env() {
  if [[ ! -f "$http_env_file" ]]; then
    cp .env.http.example "$http_env_file"
    echo "已根据 .env.http.example 创建 ${http_env_file}。"
  fi
  replace_generated_secret POSTGRES_PASSWORD
  replace_generated_secret APP_STORAGE_SECRET_KEY
  if ! grep -Eq '^[[:space:]]*FRONTEND_BIND_ADDRESS[[:space:]]*=' "$http_env_file"; then
    printf '\nFRONTEND_BIND_ADDRESS=0.0.0.0\n' >>"$http_env_file"
    echo "已为旧版 .env.http 补充 FRONTEND_BIND_ADDRESS=0.0.0.0。"
  fi
  chmod 600 "$http_env_file"
}

compose() {
  COMPOSE_PROFILES="" docker compose \
    --project-name "$compose_project" \
    --env-file "$http_env_file" \
    -f docker-compose.yml \
    "$@"
}

validate_docker_architecture() {
  local architecture
  architecture="$(docker info --format '{{.Architecture}}' 2>/dev/null || true)"
  case "$architecture" in
    amd64|x86_64|arm64|aarch64) ;;
    "") fail "无法读取 Docker daemon 架构。" ;;
    *) fail "当前 Docker 架构 ${architecture} 不受生产镜像支持；支持 linux/amd64 和 linux/arm64。" ;;
  esac
}

configured_port() {
  local name="$1"
  local default_value="$2"
  local line value
  line="$(grep -E "^[[:space:]]*${name}[[:space:]]*=" "$http_env_file" 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$default_value"
    return
  fi
  value="${line#*=}"
  value="${value%%#*}"
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^['\"'\'']//' -e 's/['\"'\'']$//')"
  if [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
    printf '%s\n' "$value"
    return
  fi
  printf '%s\n' "$default_value"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | grep -Eq "[:.]${port}[[:space:]]"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
  else
    return 1
  fi
}

check_port_conflicts() {
  if [[ -n "$(compose ps -q 2>/dev/null || true)" ]]; then
    return
  fi

  local record name port label
  local -a conflicts=()
  while IFS= read -r record; do
    IFS='|' read -r name port label <<<"$record"
    if port_in_use "$port"; then
      conflicts+=("${label} ${port}（${name}）")
    fi
  done < <(
    printf '%s\n' \
      "FRONTEND_PORT|$(configured_port FRONTEND_PORT 18073)|前端"
  )

  if (( ${#conflicts[@]} == 0 )); then
    return
  fi

  echo "检测到 HTTP 验收实例端口被占用：" >&2
  printf '  - %s\n' "${conflicts[@]}" >&2
  fail "请修改 .env.http 中对应的宿主机端口后重试。"
}

if [[ $# -gt 0 ]]; then
  echo "用法: ./scripts/start-http.sh" >&2
  exit 2
fi

command -v docker >/dev/null 2>&1 || fail "未找到 Docker，请先安装 Docker Engine 和 Compose v2。"
docker compose version >/dev/null 2>&1 || fail "未找到 Docker Compose v2。"
docker info >/dev/null 2>&1 || fail "Docker daemon 未运行，或当前用户无权访问 Docker。"

ensure_http_env
validate_docker_architecture
compose config --quiet || fail "HTTP 验收 Compose 配置无效，请检查 .env.http。"
check_port_conflicts

echo "正在启动隔离的 HTTP 验收实例..."
compose up -d --build --wait

frontend_port="$(configured_port FRONTEND_PORT 18073)"

echo
compose ps
echo
echo "服务器直连入口: http://<服务器 IP>:${frontend_port}"
echo "NAT 入口: http://<公网 IP 或域名>:<公网映射端口>"
echo "NAT 只需将该公网 TCP 端口转发到本机 ${frontend_port}。"
echo "PostgreSQL、Redis、MinIO 和 API 没有宿主机端口，不需要也不能直接做公网转发。"
echo "注意: 公网普通 HTTP 无法获得浏览器麦克风权限，文字面试和管理功能可正常验收。"
echo "停止实例: ./scripts/stop-http.sh"
