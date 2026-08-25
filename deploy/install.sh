#!/usr/bin/env bash

set -Eeuo pipefail

bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${bundle_dir}/lib.sh"

deploy_root="/opt/interview-guide"
namespace=""
channel="main"
domain=""
acme_email=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      [[ $# -ge 2 ]] || deploy_die "--root 需要目录参数。"
      deploy_root="$2"
      shift 2
      ;;
    --namespace)
      [[ $# -ge 2 ]] || deploy_die "--namespace 需要 GHCR 用户名或组织名。"
      namespace="$2"
      shift 2
      ;;
    --channel)
      [[ $# -ge 2 ]] || deploy_die "--channel 需要 tag。"
      channel="$2"
      shift 2
      ;;
    --domain)
      [[ $# -ge 2 ]] || deploy_die "--domain 需要域名参数。"
      domain="${2,,}"
      shift 2
      ;;
    --email)
      [[ $# -ge 2 ]] || deploy_die "--email 需要 ACME 联系邮箱。"
      acme_email="$2"
      shift 2
      ;;
    *) deploy_die "未知参数: $1" ;;
  esac
done

[[ ${EUID:-$(id -u)} -eq 0 ]] || deploy_die "安装 systemd 定时器需要 root，请使用 sudo。"
deploy_validate_root "$deploy_root"
deploy_validate_namespace "$namespace"
deploy_validate_tag "$channel"
deploy_validate_domain "$domain"
deploy_validate_email "$acme_email"
command -v docker >/dev/null 2>&1 || deploy_die "未找到 Docker。"
command -v systemctl >/dev/null 2>&1 || deploy_die "未找到 systemctl；主动拉取安装器要求 systemd。"
docker compose version >/dev/null 2>&1 || deploy_die "未找到 Docker Compose v2。"
docker info >/dev/null 2>&1 || deploy_die "Docker daemon 不可用。"
deploy_validate_architecture

install -d -m 0755 "$deploy_root" "${deploy_root}/bundle" "${deploy_root}/state"
install -m 0644 "${bundle_dir}/compose.yml" "${deploy_root}/bundle/compose.yml"
install -m 0644 "${bundle_dir}/Caddyfile" "${deploy_root}/bundle/Caddyfile"
for file in install.sh lib.sh refresh.sh rollback.sh status.sh stop.sh update.sh; do
  install -m 0755 "${bundle_dir}/${file}" "${deploy_root}/bundle/${file}"
done
install -d -m 0755 "${deploy_root}/bundle/systemd"
install -m 0644 \
  "${bundle_dir}/systemd/interview-guide-update.service.in" \
  "${deploy_root}/bundle/systemd/interview-guide-update.service.in"
install -m 0644 \
  "${bundle_dir}/systemd/interview-guide-update.timer" \
  "${deploy_root}/bundle/systemd/interview-guide-update.timer"

env_file="${deploy_root}/.env"
if [[ ! -f "$env_file" ]]; then
  install -m 0600 "${bundle_dir}/.env.example" "$env_file"
  deploy_replace_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_NAMESPACE "$namespace"
  deploy_replace_env_value "$env_file" INTERVIEW_GUIDE_UPDATE_CHANNEL "$channel"
  deploy_replace_env_value "$env_file" COMPOSE_PROFILES https
  deploy_replace_env_value "$env_file" PUBLIC_DOMAIN "$domain"
  deploy_replace_env_value "$env_file" ACME_EMAIL "$acme_email"
  deploy_replace_env_value "$env_file" FRONTEND_BIND_ADDRESS 127.0.0.1
  deploy_replace_env_value "$env_file" POSTGRES_PASSWORD "$(deploy_random_secret)"
  deploy_replace_env_value "$env_file" APP_STORAGE_SECRET_KEY "$(deploy_random_secret)"
  echo "已创建 ${env_file} 并生成随机基础设施密码。"
else
  chmod 600 "$env_file"
  configured_namespace="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_NAMESPACE)"
  [[ -n "$configured_namespace" ]] \
    || deploy_replace_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_NAMESPACE "$namespace"
  [[ -n "$(deploy_env_value "$env_file" INTERVIEW_GUIDE_UPDATE_CHANNEL)" ]] \
    || deploy_replace_env_value "$env_file" INTERVIEW_GUIDE_UPDATE_CHANNEL "$channel"
  deploy_replace_env_value "$env_file" COMPOSE_PROFILES https
  deploy_replace_env_value "$env_file" PUBLIC_DOMAIN "$domain"
  deploy_replace_env_value "$env_file" ACME_EMAIL "$acme_email"
  deploy_replace_env_value "$env_file" FRONTEND_BIND_ADDRESS 127.0.0.1
  [[ -n "$(deploy_env_value "$env_file" POSTGRES_PASSWORD)" ]] \
    || deploy_replace_env_value "$env_file" POSTGRES_PASSWORD "$(deploy_random_secret)"
  [[ -n "$(deploy_env_value "$env_file" APP_STORAGE_SECRET_KEY)" ]] \
    || deploy_replace_env_value "$env_file" APP_STORAGE_SECRET_KEY "$(deploy_random_secret)"
  echo "保留已有部署配置 ${env_file}。"
fi

service_tmp="$(mktemp)"
trap 'rm -f "$service_tmp"' EXIT
sed "s|@DEPLOY_ROOT@|${deploy_root}|g" \
  "${bundle_dir}/systemd/interview-guide-update.service.in" >"$service_tmp"
install -m 0644 "$service_tmp" /etc/systemd/system/interview-guide-update.service
install -m 0644 \
  "${bundle_dir}/systemd/interview-guide-update.timer" \
  /etc/systemd/system/interview-guide-update.timer

echo "执行首次 GHCR 拉取和部署..."
"${deploy_root}/bundle/refresh.sh" --root "$deploy_root"

systemctl daemon-reload
systemctl enable --now interview-guide-update.timer

echo
echo "主动拉取部署已安装。"
echo "配置文件: ${env_file}"
echo "HTTPS 入口: https://${domain}"
echo "状态命令: ${deploy_root}/bundle/status.sh --root ${deploy_root}"
echo "更新日志: journalctl -u interview-guide-update.service"
echo "定时器:    systemctl list-timers interview-guide-update.timer"
