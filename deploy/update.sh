#!/usr/bin/env bash

set -Eeuo pipefail

bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${bundle_dir}/lib.sh"

deploy_root="/opt/interview-guide"
candidate_tag=""
lock_held=false
force=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      [[ $# -ge 2 ]] || deploy_die "--root 需要目录参数。"
      deploy_root="$2"
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || deploy_die "--tag 需要镜像 tag。"
      candidate_tag="$2"
      shift 2
      ;;
    --force)
      force=true
      shift
      ;;
    --lock-held)
      lock_held=true
      shift
      ;;
    *) deploy_die "未知参数: $1" ;;
  esac
done

deploy_validate_root "$deploy_root"
env_file="${deploy_root}/.env"
state_dir="${deploy_root}/state"
compose_file="${bundle_dir}/compose.yml"
[[ -f "$env_file" ]] || deploy_die "缺少部署配置: ${env_file}"
[[ -f "$compose_file" ]] || deploy_die "缺少部署清单: ${compose_file}"

command -v docker >/dev/null 2>&1 || deploy_die "未找到 Docker。"
docker compose version >/dev/null 2>&1 || deploy_die "未找到 Docker Compose v2。"
docker info >/dev/null 2>&1 || deploy_die "Docker daemon 不可用。"
deploy_validate_architecture

namespace="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_NAMESPACE)"
registry="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_REGISTRY ghcr.io)"
project_name="$(deploy_env_value "$env_file" COMPOSE_PROJECT_NAME interview-guide)"
compose_profiles="$(deploy_env_value "$env_file" COMPOSE_PROFILES)"
external_caddy="$(deploy_env_value "$env_file" EXTERNAL_CADDY false)"
[[ "$external_caddy" == true || "$external_caddy" == false ]] \
  || deploy_die "EXTERNAL_CADDY 只能设置为 true 或 false。"
if [[ "$external_caddy" == true ]] && deploy_https_enabled "$compose_profiles"; then
  deploy_die "EXTERNAL_CADDY=true 时不能同时启用 Compose https profile。"
fi
if [[ "$external_caddy" == true ]]; then
  frontend_bind_address="$(deploy_env_value "$env_file" FRONTEND_BIND_ADDRESS 127.0.0.1)"
  [[ "$frontend_bind_address" == 127.0.0.1 ]] \
    || deploy_die "复用宿主机 Caddy 时 FRONTEND_BIND_ADDRESS 必须是 127.0.0.1。"
fi
deploy_validate_namespace "$namespace"
[[ "$registry" =~ ^[A-Za-z0-9.-]+(:[0-9]+)?$ ]] || deploy_die "镜像仓库地址无效: ${registry}"
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]{0,62}$ ]] || deploy_die "Compose 项目名无效: ${project_name}"

https_enabled=false
bundled_https=false
public_domain=""
if deploy_https_enabled "$compose_profiles"; then
  https_enabled=true
  bundled_https=true
fi
if [[ "$external_caddy" == true ]]; then
  https_enabled=true
fi
if [[ "$https_enabled" == true ]]; then
  public_domain="$(deploy_env_value "$env_file" PUBLIC_DOMAIN)"
  deploy_validate_domain "$public_domain"
fi
if [[ "$bundled_https" == true ]]; then
  acme_email="$(deploy_env_value "$env_file" ACME_EMAIL)"
  deploy_validate_email "$acme_email"
fi

mkdir -p "$state_dir"
if [[ -z "$candidate_tag" ]]; then
  candidate_tag="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_TAG main)"
fi
deploy_validate_tag "$candidate_tag"

lock_dir=""
if [[ "$lock_held" != true ]]; then
  lock_dir="$(deploy_acquire_lock "$deploy_root")"
  trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT
fi

current_tag=""
if [[ -f "${state_dir}/current-tag" ]]; then
  current_tag="$(tr -d '\r\n' <"${state_dir}/current-tag")"
fi
compose() {
  COMPOSE_PROFILES="$compose_profiles" \
    INTERVIEW_GUIDE_IMAGE_TAG="$candidate_tag" \
    docker compose \
    --project-name "$project_name" \
    --project-directory "$deploy_root" \
    --env-file "$env_file" \
    -f "$compose_file" \
    "$@"
}

verify_https() {
  local attempt
  for attempt in {1..36}; do
    if compose exec -T app python -c \
      "import urllib.request; urllib.request.urlopen('https://${public_domain}/health', timeout=4).read()" \
      >/dev/null 2>&1; then
      return
    fi
    if (( attempt % 6 == 0 )); then
      echo "仍在等待 Let's Encrypt 证书和 HTTPS 健康检查（${attempt}/36）..."
    fi
    sleep 5
  done
  compose logs --tail=120 gateway frontend app >&2 || true
  deploy_die "HTTPS 验证失败。请检查域名解析、公网 80/443、防火墙和 Caddy 日志。"
}

verify_external_https() {
  command -v curl >/dev/null 2>&1 \
    || deploy_die "复用宿主机 Caddy 时需要安装 curl 以验证 HTTPS。"
  local attempt
  for attempt in {1..36}; do
    if curl --fail --silent --show-error \
      --noproxy '*' \
      --resolve "${public_domain}:443:127.0.0.1" \
      "https://${public_domain}/health" >/dev/null 2>&1; then
      return
    fi
    if (( attempt % 6 == 0 )); then
      echo "仍在等待宿主机 Caddy 证书和 HTTPS 健康检查（${attempt}/36）..."
    fi
    sleep 5
  done
  compose logs --tail=120 frontend app >&2 || true
  deploy_die "宿主机 Caddy HTTPS 验证失败。请检查 Caddyfile、证书和 127.0.0.1 前端上游。"
}

verify_public_https() {
  if [[ "$external_caddy" == true ]]; then
    verify_external_https
  else
    verify_https
  fi
}

if [[ "$force" != true && "$candidate_tag" == "$current_tag" ]]; then
  echo "当前已经是 ${candidate_tag}，检查服务状态..."
  compose up -d --wait
  if [[ "$https_enabled" == true ]]; then
    verify_public_https
  fi
  echo "服务状态已收敛。"
  exit 0
fi

echo "准备部署 InterviewGuide ${candidate_tag}..."
compose config --quiet
compose pull

expected_revision="${candidate_tag#sha-}"
if [[ "$candidate_tag" == sha-* ]]; then
  backend_image="${registry}/${namespace}/interview-guide-backend:${candidate_tag}"
  frontend_image="${registry}/${namespace}/interview-guide-frontend:${candidate_tag}"
  backend_revision="$(docker image inspect "$backend_image" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
  frontend_revision="$(docker image inspect "$frontend_image" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
  [[ "$backend_revision" == "$expected_revision" ]] \
    || deploy_die "后端镜像 revision 与 tag 不一致。"
  [[ "$frontend_revision" == "$expected_revision" ]] \
    || deploy_die "前端镜像 revision 与 tag 不一致。"
fi

# 先保持基础设施健康，再强制重新执行一次 Bucket 初始化和 Alembic。
compose up -d --wait postgres redis minio
compose rm --stop --force createbuckets migrate >/dev/null 2>&1 || true

if ! compose up -d --wait; then
  echo "部署 ${candidate_tag} 失败，当前成功版本记录保持为 ${current_tag:-未设置}。" >&2
  if [[ -n "$current_tag" && "$current_tag" != "$candidate_tag" ]]; then
    echo "尝试恢复上一应用版本 ${current_tag}（不回滚数据库迁移）..." >&2
    rollback_services=(app worker scheduler frontend)
    if [[ "$bundled_https" == true ]]; then
      rollback_services+=(gateway)
    fi
    COMPOSE_PROFILES="$compose_profiles" \
      INTERVIEW_GUIDE_IMAGE_TAG="$current_tag" \
      docker compose \
      --project-name "$project_name" \
      --project-directory "$deploy_root" \
      --env-file "$env_file" \
      -f "$compose_file" \
      up -d --no-deps --force-recreate "${rollback_services[@]}" || true
  fi
  exit 1
fi

if [[ "$https_enabled" == true ]]; then
  verify_public_https
fi

if [[ -n "$current_tag" && "$current_tag" != "$candidate_tag" ]]; then
  deploy_write_state "${state_dir}/previous-tag" "$current_tag"
fi
deploy_write_state "${state_dir}/current-tag" "$candidate_tag"
deploy_write_state "${state_dir}/last-successful-update" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo
compose ps
echo
echo "部署成功: ${candidate_tag}"
if [[ "$https_enabled" == true ]]; then
  if [[ "$external_caddy" == true ]]; then
    echo "HTTPS 入口: https://${public_domain}（宿主机 Caddy）"
  else
    echo "HTTPS 入口: https://${public_domain}"
  fi
else
  echo "HTTP 兼容入口: $(deploy_env_value "$env_file" FRONTEND_PORT 5173)"
fi
