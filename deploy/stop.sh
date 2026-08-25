#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${script_dir}/lib.sh"

deploy_root="/opt/interview-guide"
if [[ ${1:-} == "--root" ]]; then
  [[ $# -eq 2 ]] || deploy_die "用法: stop.sh [--root /absolute/path]"
  deploy_root="$2"
elif [[ $# -gt 0 ]]; then
  deploy_die "用法: stop.sh [--root /absolute/path]"
fi
deploy_validate_root "$deploy_root"

env_file="${deploy_root}/.env"
[[ -f "$env_file" ]] || deploy_die "缺少部署配置: ${env_file}"
project_name="$(deploy_env_value "$env_file" COMPOSE_PROJECT_NAME interview-guide)"
compose_profiles="$(deploy_env_value "$env_file" COMPOSE_PROFILES)"
tag="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_TAG main)"
if [[ -f "${deploy_root}/state/current-tag" ]]; then
  tag="$(tr -d '\r\n' <"${deploy_root}/state/current-tag")"
fi

compose() {
  COMPOSE_PROFILES="$compose_profiles" \
    INTERVIEW_GUIDE_IMAGE_TAG="$tag" \
    docker compose \
    --project-name "$project_name" \
    --project-directory "$deploy_root" \
    --env-file "$env_file" \
    -f "${script_dir}/compose.yml" \
    "$@"
}

compose down --remove-orphans

echo "服务已关闭，数据卷和 Provider 加密主密钥均已保留。"
echo "如需长期保持停服，请同时禁用 interview-guide-update.timer，否则下次主动更新会重新启动服务。"
