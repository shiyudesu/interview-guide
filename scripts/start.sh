#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

open_browser=true
assume_yes=false
docker_with_sudo=false
frontend_url="http://localhost"
for argument in "$@"; do
  case "$argument" in
    --no-open) open_browser=false ;;
    --yes|-y) assume_yes=true ;;
    *)
      echo "用法: ./scripts/start.sh [--yes] [--no-open]" >&2
      exit 2
      ;;
  esac
done

fail() {
  echo
  echo "启动失败: $1" >&2
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
  if ! grep -Eq "^${name}=(GENERATE_ON_FIRST_START)?$" .env; then
    return
  fi
  value="$(random_secret)"
  temporary_file="$(mktemp)"
  awk \
    -v empty_target="${name}=" \
    -v legacy_target="${name}=GENERATE_ON_FIRST_START" \
    -v replacement="${name}=${value}" \
    '$0 == empty_target || $0 == legacy_target { print replacement; next } { print }' \
    .env >"$temporary_file"
  mv "$temporary_file" .env
}

ensure_environment_file() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "已根据 .env.example 创建 .env。"
  fi
  replace_generated_secret POSTGRES_PASSWORD
  replace_generated_secret APP_STORAGE_SECRET_KEY
  chmod 600 .env
}

validate_docker_architecture() {
  local architecture
  architecture="$(docker_cli info --format '{{.Architecture}}' 2>/dev/null || true)"
  case "$architecture" in
    amd64|x86_64|arm64|aarch64) ;;
    "") fail "无法读取 Docker daemon 架构。" ;;
    *) fail "当前 Docker 架构 ${architecture} 不受生产镜像支持；支持 linux/amd64 和 linux/arm64。" ;;
  esac
}

show_diagnostics() {
  echo
  echo "容器状态:"
  docker_cli compose ps -a || true
  echo
  echo "关键日志（最近 80 行）:"
  docker_cli compose logs --tail=80 migrate app worker scheduler frontend gateway || true
}

docker_cli() {
  if [[ "$docker_with_sudo" == true ]]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

confirm_install() {
  local description="$1"
  if [[ "$assume_yes" == true ]]; then
    return
  fi
  if [[ ! -t 0 ]]; then
    fail "需要安装 ${description}，但当前无法交互确认。请重新运行：./scripts/start.sh --yes"
  fi
  read -r -p "未检测到 ${description}，是否现在自动安装？[Y/n] " answer
  case "${answer:-Y}" in
    y|Y|yes|YES|Yes) ;;
    *) fail "已取消安装 ${description}。" ;;
  esac
}

run_as_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    fail "安装需要管理员权限，但未找到 sudo。请联系系统管理员安装 Docker。"
  fi
}

is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null
}

delegate_to_windows() {
  command -v powershell.exe >/dev/null 2>&1 || return 1
  command -v wslpath >/dev/null 2>&1 || return 1
  confirm_install "Docker Desktop"
  local windows_script
  windows_script="$(wslpath -w "$repository_root/scripts/start.ps1")"
  local -a powershell_arguments=(
    -NoProfile
    -ExecutionPolicy Bypass
    -File "$windows_script"
    -Yes
  )
  if [[ "$open_browser" != true ]]; then
    powershell_arguments+=(-NoOpen)
  fi
  powershell.exe "${powershell_arguments[@]}"
  exit $?
}

install_docker_linux() {
  [[ -r /etc/os-release ]] || fail "无法识别 Linux 发行版，请按官方文档安装 Docker：https://docs.docker.com/engine/install/"
  # shellcheck disable=SC1091
  source /etc/os-release
  local distribution="${ID:-}"
  if [[ "$distribution" != "ubuntu" && "$distribution" != "debian" ]]; then
    fail "暂不支持自动安装 ${PRETTY_NAME:-当前 Linux}。请按官方文档安装 Docker：https://docs.docker.com/engine/install/"
  fi
  confirm_install "Docker Engine 和 Docker Compose"
  run_as_root apt-get update
  run_as_root apt-get install -y ca-certificates curl
  run_as_root install -m 0755 -d /etc/apt/keyrings
  run_as_root curl -fsSL "https://download.docker.com/linux/${distribution}/gpg" -o /etc/apt/keyrings/docker.asc
  run_as_root chmod a+r /etc/apt/keyrings/docker.asc
  local architecture codename repository
  architecture="$(dpkg --print-architecture)"
  codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  [[ -n "$codename" ]] || fail "无法识别发行版代号，请按 Docker 官方文档手工安装。"
  repository="deb [arch=${architecture} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${distribution} ${codename} stable"
  printf '%s\n' "$repository" | run_as_root tee /etc/apt/sources.list.d/docker.list >/dev/null
  run_as_root apt-get update
  run_as_root apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  if command -v systemctl >/dev/null 2>&1; then
    run_as_root systemctl enable --now docker || true
  elif command -v service >/dev/null 2>&1; then
    run_as_root service docker start || true
  fi
  if [[ ${EUID:-$(id -u)} -ne 0 ]] && ! docker info >/dev/null 2>&1; then
    run_as_root usermod -aG docker "$USER"
    docker_with_sudo=true
    echo "已将当前用户加入 docker 组；本次启动会使用 sudo，重新登录后无需 sudo。"
  fi
}

load_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    return
  fi
  for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$brew_path" ]]; then
      eval "$("$brew_path" shellenv)"
      return
    fi
  done
}

install_docker_macos() {
  confirm_install "Docker Desktop"
  if [[ -d /Applications/Docker.app ]]; then
    export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
    open -a Docker
    return
  fi
  load_homebrew
  if ! command -v brew >/dev/null 2>&1; then
    command -v curl >/dev/null 2>&1 || fail "自动安装 Homebrew 需要 curl。请先安装 Xcode Command Line Tools。"
    echo "未找到 Homebrew，将先运行 Homebrew 官方安装程序。"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    load_homebrew
  fi
  command -v brew >/dev/null 2>&1 || fail "Homebrew 安装完成但当前终端尚未加载，请重新打开终端后重试。"
  if brew list --cask docker >/dev/null 2>&1; then
    brew upgrade --cask docker || true
  else
    brew install --cask docker
  fi
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
  open -a Docker
}

install_docker() {
  if is_wsl && delegate_to_windows; then
    return
  fi
  case "$(uname -s)" in
    Linux) install_docker_linux ;;
    Darwin) install_docker_macos ;;
    *) fail "当前系统不支持自动安装，请访问：https://docs.docker.com/desktop/" ;;
  esac
}

start_docker_daemon() {
  case "$(uname -s)" in
    Darwin)
      open -a Docker 2>/dev/null || true
      ;;
    Linux)
      if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command 'Start-Process "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"' >/dev/null 2>&1 || true
      elif command -v systemctl >/dev/null 2>&1; then
        run_as_root systemctl start docker || true
      elif command -v service >/dev/null 2>&1; then
        run_as_root service docker start || true
      fi
      ;;
  esac
}

wait_for_docker() {
  local attempt
  for attempt in {1..60}; do
    if docker_cli info >/dev/null 2>&1; then
      return
    fi
    if [[ "$docker_with_sudo" != true && ${EUID:-$(id -u)} -ne 0 ]] \
      && command -v sudo >/dev/null 2>&1 \
      && sudo docker info >/dev/null 2>&1; then
      docker_with_sudo=true
      echo "当前终端尚未获得 docker 组权限，本次启动将使用 sudo。"
      return
    fi
    if (( attempt % 10 == 0 )); then
      echo "仍在等待 Docker 就绪（${attempt}/60）..."
    fi
    sleep 2
  done
  fail "Docker 已安装但未能在 120 秒内启动。请查看 Docker Desktop 或 Docker 服务状态。"
}

configured_port() {
  local name="$1"
  local default_value="$2"
  local line value
  line="$(grep -E "^[[:space:]]*${name}[[:space:]]*=" .env 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$default_value"
    return
  fi
  value="${line#*=}"
  value="${value%%#*}"
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^['\"'\'']//' -e 's/['\"'\'']$//')"
  if [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

configured_value() {
  local name="$1"
  local default_value="${2:-}"
  local line value
  line="$(grep -E "^[[:space:]]*${name}[[:space:]]*=" .env 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$default_value"
    return
  fi
  value="${line#*=}"
  value="${value%%#*}"
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^['\"'\'']//' -e 's/['\"'\'']$//')"
  printf '%s\n' "${value:-$default_value}"
}

https_enabled() {
  local profiles
  profiles="$(configured_value COMPOSE_PROFILES)"
  profiles="${profiles//[[:space:]]/}"
  profiles=",${profiles},"
  [[ "$profiles" == *,https,* ]]
}

validate_https_configuration() {
  local domain email
  domain="$(configured_value PUBLIC_DOMAIN)"
  email="$(configured_value ACME_EMAIL)"
  [[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ \
    && "$domain" == *.* \
    && "$domain" != *..* \
    && "$domain" != *:* \
    && "$domain" != */* ]] \
    || fail "HTTPS 已启用，但 PUBLIC_DOMAIN 不是有效的备案域名。不要包含协议、端口或路径。"
  [[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] \
    || fail "HTTPS 已启用，但 ACME_EMAIL 未设置为有效邮箱。"
}

suggested_port() {
  local name="$1"
  local current="$2"
  local suggestion
  case "$name" in
    FRONTEND_PORT) suggestion=5174 ;;
    TLS_HTTP_PORT) suggestion=8080 ;;
    TLS_HTTPS_PORT) suggestion=8443 ;;
    *) suggestion=$((current + 10000)) ;;
  esac
  if (( suggestion == current )); then
    suggestion=$((current + 1000))
  fi
  if (( suggestion > 65535 )); then
    suggestion=$((current > 1000 ? current - 1000 : current + 1))
  fi
  local attempts=0
  while port_in_use "$suggestion" && (( attempts < 20 )); do
    suggestion=$((suggestion + 1))
    ((suggestion > 65535)) && suggestion=1024
    attempts=$((attempts + 1))
  done
  printf '%s\n' "$suggestion"
}

port_in_use() {
  local port="$1"
  if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort ${port} -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" </dev/null >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | grep -Eq "[:.]${port}[[:space:]]"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
  else
    return 1
  fi
}

show_port_owner() {
  local port="$1"
  if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -First 3 LocalAddress,LocalPort,OwningProcess | Format-Table -HideTableHeaders" 2>/dev/null | sed 's/^/    /' || true
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -E "[:.]${port}[[:space:]]" | head -n 3 | sed 's/^/    /' || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 4 | sed 's/^/    /' || true
  fi
}

port_records() {
  printf '%s\n' "FRONTEND_PORT|$(configured_port FRONTEND_PORT 5173)|本机前端诊断入口"
  if https_enabled; then
    printf '%s\n' \
      "TLS_HTTP_PORT|$(configured_port TLS_HTTP_PORT 80)|HTTPS 跳转/ACME 入口" \
      "TLS_HTTPS_PORT|$(configured_port TLS_HTTPS_PORT 443)|HTTPS 入口"
  fi
}

show_port_guidance() {
  echo
  echo "检测到宿主机端口占用。请编辑 .env 修改以下映射："
  local record name port label suggestion
  for record in "$@"; do
    IFS='|' read -r name port label <<<"$record"
    suggestion="$(suggested_port "$name" "$port")"
    echo "- ${label}: 端口 ${port} 已被占用，建议设置 ${name}=${suggestion}"
    show_port_owner "$port"
  done
  echo
  echo "修改 .env 后重新运行 ./scripts/start.sh。容器内部端口无需修改。"
  echo "HTTPS 模式下，如果宿主机不是直接使用 80/443，必须确保公网 80/443 正确转发到对应宿主机端口。"
}

show_registry_guidance() {
  echo
  echo "检测到 Docker 镜像仓库网络或 DNS 解析失败。"
  echo "- Docker Desktop：在 Settings > Resources > Proxies 配置可用代理，"
  echo "  然后重启 Docker Desktop。"
  echo "- Linux Docker Engine：为 docker daemon 配置代理，或配置可信的 Docker Hub"
  echo "  registry mirror 后重启 Docker。"
  echo "- 如果已有可信的 Docker Hub pull-through cache，也可以在 .env 中设置："
  echo "    INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=mirror.example.com"
  echo "  只填写主机名和可选路径，不要包含 https://；不要使用来源不明的公共镜像站。"
  echo "修复 daemon 网络后可运行 'docker pull docker.io/library/redis:7.4.2-alpine' 验证。"
  echo "使用 .env 来源覆盖时，运行 'docker compose config --images' 确认镜像地址。"
  echo "详细配置见 docs/OPERATIONS.md 的“Docker Hub 镜像拉取失败”章节。"
}

check_port_conflicts() {
  if [[ -n "$(docker_cli compose ps -q 2>/dev/null || true)" ]]; then
    return
  fi
  local -a conflicts=()
  local -a records=()
  local record name port label
  while IFS= read -r record; do
    records+=("$record")
  done < <(port_records)
  if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
    local requested_ports=""
    for record in "${records[@]}"; do
      IFS='|' read -r name port label <<<"$record"
      requested_ports+="${requested_ports:+,}${port}"
    done
    local busy_ports
    busy_ports="$(powershell.exe -NoProfile -Command "\$wanted = @(${requested_ports}); Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { \$wanted -contains \$_.LocalPort } | Select-Object -ExpandProperty LocalPort -Unique" </dev/null 2>/dev/null | tr -d '\r' || true)"
    for record in "${records[@]}"; do
      IFS='|' read -r name port label <<<"$record"
      if printf '%s\n' "$busy_ports" | grep -qx "$port"; then
        conflicts+=("$record")
      fi
    done
  else
    for record in "${records[@]}"; do
      IFS='|' read -r name port label <<<"$record"
      if port_in_use "$port"; then
        conflicts+=("$record")
      fi
    done
  fi
  if (( ${#conflicts[@]} > 0 )); then
    show_port_guidance "${conflicts[@]}"
    fail "请先解决端口占用。"
  fi
}

diagnose_compose_failure() {
  local log_file="$1"
  local registry_pattern network_pattern
  registry_pattern='registry-1\.docker\.io|auth\.docker\.io'
  registry_pattern+='|production\.cloudflare\.docker\.com|docker\.io/'
  registry_pattern+='|failed to resolve source metadata|failed to fetch anonymous token'
  network_pattern='lookup |no such host|server misbehaving|temporary failure in name resolution'
  network_pattern+='|dial tcp|connectex|i/o timeout|TLS handshake timeout'
  network_pattern+='|context deadline exceeded|network is unreachable|connection refused'
  network_pattern+='|connection reset|failed to do request|unexpected EOF'
  if grep -Eqi "$registry_pattern" "$log_file" \
    && grep -Eqi "$network_pattern" "$log_file"; then
    show_registry_guidance
  fi

  if grep -Eqi 'port is already allocated|address already in use|failed to bind host port|bind for .* failed' "$log_file"; then
    local -a matches=()
    local record name port label
    while IFS= read -r record; do
      IFS='|' read -r name port label <<<"$record"
      if grep -Eq "[:.]${port}([^0-9]|$)" "$log_file"; then
        matches+=("$record")
      fi
    done < <(port_records)
    if (( ${#matches[@]} == 0 )); then
      while IFS= read -r record; do
        matches+=("$record")
      done < <(port_records)
    fi
    show_port_guidance "${matches[@]}"
  fi
}

open_frontend() {
  if [[ "$open_browser" != true ]]; then
    return
  fi
  if grep -qi microsoft /proc/version 2>/dev/null && command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$frontend_url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$frontend_url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$frontend_url" >/dev/null 2>&1 || true
  fi
}

echo "检查本地运行环境..."

if ! command -v docker >/dev/null 2>&1; then
  install_docker
  command -v docker >/dev/null 2>&1 || fail "Docker 安装完成，但当前终端仍找不到 docker 命令。请重新打开终端后重试。"
fi

if ! docker_cli compose version >/dev/null 2>&1; then
  install_docker
  docker_cli compose version >/dev/null 2>&1 || fail "Docker Compose v2 安装后仍不可用，请重新打开终端后重试。"
fi

if ! docker_cli info >/dev/null 2>&1; then
  echo "Docker daemon 未运行，正在尝试启动..."
  start_docker_daemon
  wait_for_docker
fi

ensure_environment_file
validate_docker_architecture
export COMPOSE_PROFILES="$(configured_value COMPOSE_PROFILES)"

use_https=false
if https_enabled; then
  use_https=true
  validate_https_configuration
fi

if ! docker_cli compose config --quiet; then
  fail "Compose 配置无效，请检查 .env。"
fi

frontend_port="$(configured_port FRONTEND_PORT 5173)"
if [[ "$use_https" == true ]]; then
  public_domain="$(configured_value PUBLIC_DOMAIN)"
  https_port="$(configured_port TLS_HTTPS_PORT 443)"
  if [[ "$https_port" == "443" ]]; then
    frontend_url="https://${public_domain}"
  else
    frontend_url="https://${public_domain}:${https_port}"
  fi
elif [[ "$frontend_port" == "80" ]]; then
  frontend_url="http://localhost"
else
  frontend_url="http://localhost:${frontend_port}"
fi

check_port_conflicts

echo "构建并启动服务，首次运行需要下载镜像和依赖，请稍候..."
startup_log="$(mktemp)"
trap 'rm -f "$startup_log"' EXIT
if ! docker_cli compose up -d --build --wait 2>&1 | tee "$startup_log"; then
  diagnose_compose_failure "$startup_log"
  show_diagnostics
  fail "Compose 启动未完成。请根据上方日志修复后重试。"
fi
rm -f "$startup_log"
trap - EXIT

echo
echo "启动成功。"
docker_cli compose ps
echo
echo "前端:   ${frontend_url}"
echo "设置页: ${frontend_url}/settings"
echo "API 文档: ${frontend_url}/docs"
echo "OpenAPI:  ${frontend_url}/openapi.json"
if [[ "$use_https" == true ]]; then
  echo "TLS:      Caddy 将通过 Let's Encrypt 自动签发和续期证书"
fi
echo
echo "首次使用请在设置页编辑 dashscope，并录入百炼 API Key。"
echo "停止服务: ./scripts/stop.sh"

open_frontend
