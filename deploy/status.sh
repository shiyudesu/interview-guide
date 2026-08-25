#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${script_dir}/lib.sh"

deploy_root="/opt/interview-guide"
if [[ ${1:-} == "--root" ]]; then
  [[ $# -eq 2 ]] || deploy_die "用法: status.sh [--root /absolute/path]"
  deploy_root="$2"
elif [[ $# -gt 0 ]]; then
  deploy_die "用法: status.sh [--root /absolute/path]"
fi
deploy_validate_root "$deploy_root"

env_file="${deploy_root}/.env"
[[ -f "$env_file" ]] || deploy_die "缺少部署配置: ${env_file}"
project_name="$(deploy_env_value "$env_file" COMPOSE_PROJECT_NAME interview-guide)"
compose_profiles="$(deploy_env_value "$env_file" COMPOSE_PROFILES)"
external_caddy="$(deploy_env_value "$env_file" EXTERNAL_CADDY false)"
tag="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_TAG main)"
if [[ -f "${deploy_root}/state/current-tag" ]]; then
  tag="$(tr -d '\r\n' <"${deploy_root}/state/current-tag")"
fi

echo "当前版本: ${tag}"
if [[ -f "${deploy_root}/state/previous-tag" ]]; then
  echo "上一版本: $(tr -d '\r\n' <"${deploy_root}/state/previous-tag")"
fi
if [[ -f "${deploy_root}/state/last-successful-update" ]]; then
  echo "最近更新: $(tr -d '\r\n' <"${deploy_root}/state/last-successful-update")"
fi
if deploy_https_enabled "$compose_profiles"; then
  echo "HTTPS 入口: https://$(deploy_env_value "$env_file" PUBLIC_DOMAIN)"
elif [[ "$external_caddy" == true ]]; then
  echo "HTTPS 入口: https://$(deploy_env_value "$env_file" PUBLIC_DOMAIN)（宿主机 Caddy）"
else
  echo "入口模式: 兼容 HTTP；正式公网部署应切换到 HTTPS。"
fi
echo
COMPOSE_PROFILES="$compose_profiles" \
  INTERVIEW_GUIDE_IMAGE_TAG="$tag" \
  docker compose \
  --project-name "$project_name" \
  --project-directory "$deploy_root" \
  --env-file "$env_file" \
  -f "${script_dir}/compose.yml" \
  ps -a
