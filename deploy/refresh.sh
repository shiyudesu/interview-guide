#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${script_dir}/lib.sh"

deploy_root="/opt/interview-guide"
if [[ ${1:-} == "--root" ]]; then
  [[ $# -eq 2 ]] || deploy_die "用法: refresh.sh [--root /absolute/path]"
  deploy_root="$2"
elif [[ $# -gt 0 ]]; then
  deploy_die "用法: refresh.sh [--root /absolute/path]"
fi

deploy_validate_root "$deploy_root"
env_file="${deploy_root}/.env"
[[ -f "$env_file" ]] || deploy_die "缺少部署配置: ${env_file}"
command -v docker >/dev/null 2>&1 || deploy_die "未找到 Docker。"
docker info >/dev/null 2>&1 || deploy_die "Docker daemon 不可用。"

namespace="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_NAMESPACE)"
registry="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_IMAGE_REGISTRY ghcr.io)"
channel="$(deploy_env_value "$env_file" INTERVIEW_GUIDE_UPDATE_CHANNEL main)"
deploy_validate_namespace "$namespace"
deploy_validate_tag "$channel"

lock_dir="$(deploy_acquire_lock "$deploy_root")"
container_id=""
next_dir=""
cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  if [[ -n "$next_dir" && -d "$next_dir" ]]; then
    rm -rf -- "$next_dir"
  fi
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT

bundle_image="${registry}/${namespace}/interview-guide-deploy:${channel}"
echo "检查部署通道 ${bundle_image}..."
docker pull --quiet "$bundle_image" >/dev/null
revision="$(docker image inspect "$bundle_image" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
[[ "$revision" =~ ^[0-9a-f]{40,64}$ ]] || deploy_die "部署包缺少有效的源码 revision。"
candidate_tag="sha-${revision}"

current_tag=""
if [[ -f "${deploy_root}/state/current-tag" ]]; then
  current_tag="$(tr -d '\r\n' <"${deploy_root}/state/current-tag")"
fi
bundle_revision=""
if [[ -f "${deploy_root}/state/bundle-revision" ]]; then
  bundle_revision="$(tr -d '\r\n' <"${deploy_root}/state/bundle-revision")"
fi
if [[ "$candidate_tag" == "$current_tag" && "$revision" == "$bundle_revision" ]]; then
  echo "通道 ${channel} 没有新版本，检查现有服务状态。"
  "${deploy_root}/bundle/update.sh" \
    --root "$deploy_root" \
    --tag "$candidate_tag" \
    --lock-held
  exit 0
fi

next_dir="$(mktemp -d "${deploy_root}/.bundle.next.XXXXXX")"
container_id="$(docker create "$bundle_image")"
docker cp "${container_id}:/bundle/." "$next_dir/"
docker rm "$container_id" >/dev/null
container_id=""
chmod 755 "$next_dir"/*.sh
[[ -f "$next_dir/compose.yml" && -f "$next_dir/Caddyfile" && -x "$next_dir/update.sh" ]] \
  || deploy_die "部署包内容不完整。"

"${next_dir}/update.sh" \
  --root "$deploy_root" \
  --tag "$candidate_tag" \
  --lock-held

previous_bundle="${deploy_root}/state/bundle-previous"
rm -rf -- "$previous_bundle"
if [[ -d "${deploy_root}/bundle" ]]; then
  mv "${deploy_root}/bundle" "$previous_bundle"
fi
mv "$next_dir" "${deploy_root}/bundle"
next_dir=""
deploy_write_state "${deploy_root}/state/bundle-revision" "$revision"
echo "部署清单已同步到 revision ${revision}。"
