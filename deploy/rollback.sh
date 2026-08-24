#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${script_dir}/lib.sh"

deploy_root="/opt/interview-guide"
if [[ ${1:-} == "--root" ]]; then
  [[ $# -eq 2 ]] || deploy_die "用法: rollback.sh [--root /absolute/path]"
  deploy_root="$2"
elif [[ $# -gt 0 ]]; then
  deploy_die "用法: rollback.sh [--root /absolute/path]"
fi
deploy_validate_root "$deploy_root"

previous_file="${deploy_root}/state/previous-tag"
[[ -f "$previous_file" ]] || deploy_die "没有可回滚的上一版本记录。"
previous_tag="$(tr -d '\r\n' <"$previous_file")"
deploy_validate_tag "$previous_tag"

exec "${script_dir}/update.sh" --root "$deploy_root" --tag "$previous_tag" --force
