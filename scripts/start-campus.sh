#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

campus_env_file=".env.campus"
compose_project="interview-guide-campus"
assume_yes=false

fail() {
  echo "错误: $*" >&2
  exit 1
}

usage() {
  echo "用法: ./scripts/start-campus.sh [--yes]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) assume_yes=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

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
  if ! grep -Eq "^${name}=(GENERATE_ON_FIRST_START)?$" "$campus_env_file"; then
    return
  fi
  value="$(random_secret)"
  temporary_file="$(mktemp)"
  awk \
    -v empty_target="${name}=" \
    -v legacy_target="${name}=GENERATE_ON_FIRST_START" \
    -v replacement="${name}=${value}" \
    '$0 == empty_target || $0 == legacy_target { print replacement; next } { print }' \
    "$campus_env_file" >"$temporary_file"
  mv "$temporary_file" "$campus_env_file"
}

ensure_environment_file() {
  if [[ ! -f "$campus_env_file" ]]; then
    cp .env.campus.example "$campus_env_file"
    chmod 600 "$campus_env_file"
    fail "已创建 .env.campus。请填写 OpenTrek APP_KEY、工作空间和四个 Agent Code 后重试。"
  fi
  replace_generated_secret POSTGRES_PASSWORD
  replace_generated_secret APP_STORAGE_SECRET_KEY
  chmod 600 "$campus_env_file"
}

configured_value() {
  local name="$1"
  local default_value="${2:-}"
  local line value
  line="$(grep -E "^[[:space:]]*${name}[[:space:]]*=" "$campus_env_file" 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$default_value"
    return
  fi
  value="${line#*=}"
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [[ ${#value} -ge 2 && ( "$value" == \'*\' || "$value" == \"*\" ) ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s\n' "${value:-$default_value}"
}

compose() {
  COMPOSE_PROFILES="" docker compose \
    --project-name "$compose_project" \
    --env-file "$campus_env_file" \
    -f docker-compose.yml \
    "$@"
}

confirm_install() {
  if [[ "$assume_yes" == true ]]; then
    return
  fi
  [[ -t 0 ]] || fail "安装 Docker 需要确认；请在交互终端运行或显式增加 --yes。"
  read -r -p "未检测到 Docker Engine/Compose，是否安装 Docker 官方组件？[y/N] " answer
  [[ "$answer" =~ ^([yY]|yes|YES)$ ]] || fail "已取消 Docker 安装。"
}

install_docker() {
  [[ -r /etc/os-release ]] || fail "无法识别 Linux 发行版，请按 Docker 官方文档安装。"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "ubuntu" || "${ID:-}" == "debian" ]] \
    || fail "校园脚本只支持 Ubuntu/Debian；请按 Docker 官方文档安装。"
  confirm_install
  local elevate=()
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || fail "安装 Docker 需要 sudo。"
    elevate=(sudo)
  fi
  "${elevate[@]}" apt-get update
  "${elevate[@]}" apt-get install -y ca-certificates curl
  "${elevate[@]}" install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" \
    | "${elevate[@]}" tee /etc/apt/keyrings/docker.asc >/dev/null
  "${elevate[@]}" chmod a+r /etc/apt/keyrings/docker.asc
  local architecture codename repository
  architecture="$(dpkg --print-architecture)"
  codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  [[ -n "$codename" ]] || fail "无法识别发行版代号。"
  repository="deb [arch=${architecture} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${codename} stable"
  printf '%s\n' "$repository" \
    | "${elevate[@]}" tee /etc/apt/sources.list.d/docker.list >/dev/null
  "${elevate[@]}" apt-get update
  "${elevate[@]}" apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  "${elevate[@]}" systemctl enable --now docker
  if ! docker info >/dev/null 2>&1; then
    fail "Docker 已安装，但当前用户无访问权限；请加入 docker 组并重新登录后重试。"
  fi
}

validate_host() {
  [[ "$(uname -s)" == "Linux" ]] || fail "校园部署脚本只支持 Linux。"
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) fail "校园比赛完整栈只支持 x86_64/amd64 主机。" ;;
  esac
  command -v docker >/dev/null 2>&1 || install_docker
  docker compose version >/dev/null 2>&1 || install_docker
  docker info >/dev/null 2>&1 || fail "Docker daemon 未运行，或当前用户无访问权限。"
  local docker_architecture
  docker_architecture="$(docker info --format '{{.Architecture}}')"
  [[ "$docker_architecture" == "x86_64" || "$docker_architecture" == "amd64" ]] \
    || fail "Docker daemon 架构必须为 amd64，当前为 ${docker_architecture}。"
}

validate_configuration() {
  local name value
  local -a required=(
    APP_OPENTREK_APP_KEY
    APP_OPENTREK_WORKSPACE_CODE
    APP_OPENTREK_GENERAL_AGENT_CODE
    APP_OPENTREK_GENERAL_AGENT_VERSION
    APP_OPENTREK_INTERVIEWER_AGENT_CODE
    APP_OPENTREK_INTERVIEWER_AGENT_VERSION
    APP_OPENTREK_EVALUATOR_AGENT_CODE
    APP_OPENTREK_EVALUATOR_AGENT_VERSION
    APP_OPENTREK_RAG_AGENT_CODE
    APP_OPENTREK_RAG_AGENT_VERSION
  )
  for name in "${required[@]}"; do
    value="$(configured_value "$name")"
    [[ -n "$value" ]] || fail ".env.campus 缺少 ${name}。"
  done
  [[ "$(configured_value APP_COMPETITION_MODE)" == "true" ]] \
    || fail "APP_COMPETITION_MODE 必须为 true。"
  [[ "$(configured_value APP_AUTH_ENABLED)" == "true" ]] \
    || fail "校园比赛实例必须启用账号认证。"
  [[ "$(configured_value APP_AUTH_REGISTRATION_ENABLED)" == "false" ]] \
    || fail "校园比赛实例必须关闭自助注册。"
  [[ "$(configured_value APP_AUTH_COOKIE_SECURE)" == "false" ]] \
    || fail "校园 HTTP 实例必须设置 APP_AUTH_COOKIE_SECURE=false。"
  [[ "$(configured_value APP_OPENTREK_ENABLED)" == "true" ]] \
    || fail "APP_OPENTREK_ENABLED 必须为 true。"
  [[ "$(configured_value FRONTEND_BIND_ADDRESS)" == "0.0.0.0" ]] \
    || fail "校园网访问需要 FRONTEND_BIND_ADDRESS=0.0.0.0。"
  [[ "$(configured_value APP_OPENTREK_RUNTIME_BASE_URL)" == http://10.128.203.200:* ]] \
    || fail "OpenTrek Runtime URL 必须指向 10.128.203.200。"
  command -v python3 >/dev/null 2>&1 || fail "校验知识库映射需要 python3。"
  CAMPUS_KB_MAPPINGS="$(configured_value APP_OPENTREK_KB_MAPPINGS_JSON '[]')" \
    python3 -c 'import json, os; value=json.loads(os.environ["CAMPUS_KB_MAPPINGS"]); assert isinstance(value, (list, dict))' \
    || fail "APP_OPENTREK_KB_MAPPINGS_JSON 必须是 JSON 数组或对象。"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | grep -Eq "[:.]${port}[[:space:]]"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

check_frontend_port() {
  if [[ -n "$(compose ps -q 2>/dev/null || true)" ]]; then
    return
  fi
  local port
  port="$(configured_value FRONTEND_PORT 18073)"
  [[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1 && port <= 65535 )) \
    || fail "FRONTEND_PORT 必须是 1-65535。"
  if ! port_in_use "$port"; then
    return
  fi
  echo "端口 ${port} 已被占用：" >&2
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -E "[:.]${port}[[:space:]]" | head -n 5 >&2 || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 || true
  fi
  fail "请修改 .env.campus 中 FRONTEND_PORT，例如 FRONTEND_PORT=$((port + 1))。"
}

check_http_reachable() {
  local label="$1"
  local url="$2"
  local status
  status="$(curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' "$url" || true)"
  [[ "$status" != "000" && -n "$status" ]] \
    || fail "宿主机无法连接 ${label}: ${url}"
  echo "${label}: HTTP ${status}"
}

check_container_reachable() {
  local service="$1"
  compose exec -T "$service" python -c \
    'import urllib.error, urllib.request; url="http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession"; request=urllib.request.Request(url, method="POST", data=b"{}", headers={"Content-Type":"application/json"});
try: urllib.request.urlopen(request, timeout=10).read()
except urllib.error.HTTPError: pass' \
    || fail "${service} 容器无法连接 OpenTrek Runtime。"
}

show_addresses() {
  local port="$1"
  echo
  echo "评委访问地址："
  ip -4 -o addr show scope global 2>/dev/null \
    | awk -v port="$port" '{ split($4, address, "/"); print "  http://" address[1] ":" port }'
}

validate_host
ensure_environment_file
validate_configuration
compose config --quiet || fail "校园 Compose 配置无效，请检查 .env.campus。"
check_frontend_port

command -v curl >/dev/null 2>&1 || fail "网络诊断需要 curl。"
check_http_reachable "OpenTrek 管理页" "http://10.128.203.200:30226/agent/index.html"
check_http_reachable \
  "OpenTrek Runtime" \
  "http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession"

echo "正在构建并启动隔离的校园比赛实例..."
if ! compose up -d --build --wait; then
  compose ps -a || true
  compose logs --tail=100 migrate app worker scheduler frontend || true
  fail "校园实例启动失败。"
fi

check_container_reachable app
check_container_reachable worker

frontend_port="$(configured_value FRONTEND_PORT 18073)"
echo
compose ps
show_addresses "$frontend_port"
echo
echo "当前为校园网 HTTP 明文模式，不替代正式 HTTPS；请勿上传真实简历或使用个人密码。"
echo "浏览器麦克风在非安全上下文中不可用，因此校园赛版已关闭语音面试。"
echo "停止服务: ./scripts/stop-campus.sh"
