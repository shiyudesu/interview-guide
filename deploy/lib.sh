#!/usr/bin/env bash

deploy_die() {
  echo "错误: $*" >&2
  exit 1
}

deploy_env_value() {
  local env_file="$1"
  local name="$2"
  local default_value="${3:-}"
  local line value
  line="$(grep -E "^[[:space:]]*${name}[[:space:]]*=" "$env_file" 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$default_value"
    return
  fi
  value="${line#*=}"
  value="${value%%#*}"
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^['\"'\'']//' -e 's/['\"'\'']$//')"
  printf '%s\n' "${value:-$default_value}"
}

deploy_random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
    return
  fi
  od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
  printf '\n'
}

deploy_replace_env_value() {
  local env_file="$1"
  local name="$2"
  local value="$3"
  local temporary_file
  temporary_file="$(mktemp "${env_file}.tmp.XXXXXX")"
  awk \
    -v name="$name" \
    -v replacement="${name}=${value}" \
    'BEGIN { replaced = 0 }
     $0 ~ "^[[:space:]]*" name "[[:space:]]*=" {
       if (!replaced) print replacement
       replaced = 1
       next
     }
     { print }
     END { if (!replaced) print replacement }' \
    "$env_file" >"$temporary_file"
  chmod --reference="$env_file" "$temporary_file" 2>/dev/null || chmod 600 "$temporary_file"
  mv "$temporary_file" "$env_file"
}

deploy_validate_root() {
  local deploy_root="$1"
  [[ "$deploy_root" == /* ]] || deploy_die "部署目录必须是绝对路径: ${deploy_root}"
  [[ "$deploy_root" != "/" ]] || deploy_die "部署目录不能是根目录。"
  [[ "$deploy_root" =~ ^/[A-Za-z0-9._/-]+$ ]] \
    || deploy_die "部署目录只能包含字母、数字、点、下划线、短横线和斜杠: ${deploy_root}"
  [[ ! "$deploy_root" =~ (^|/)\.\.(/|$) ]] \
    || deploy_die "部署目录不能包含 .. 路径段: ${deploy_root}"
}

deploy_validate_namespace() {
  local namespace="$1"
  [[ "$namespace" =~ ^[a-z0-9][a-z0-9-]{0,99}$ ]] \
    || deploy_die "GHCR namespace 无效，应为小写 GitHub 用户名或组织名: ${namespace}"
}

deploy_validate_tag() {
  local tag="$1"
  [[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] \
    || deploy_die "镜像 tag 无效: ${tag}"
}

deploy_validate_architecture() {
  local architecture
  architecture="$(docker info --format '{{.Architecture}}' 2>/dev/null || true)"
  case "$architecture" in
    amd64|x86_64|arm64|aarch64) ;;
    "") deploy_die "无法读取 Docker daemon 架构。" ;;
    *) deploy_die "当前 Docker 架构 ${architecture} 不受支持；支持 linux/amd64 和 linux/arm64。" ;;
  esac
}

deploy_acquire_lock() {
  local deploy_root="$1"
  local lock_dir="${deploy_root}/state/update.lock"
  mkdir -p "${deploy_root}/state"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    deploy_die "已有部署更新正在运行: ${lock_dir}"
  fi
  printf '%s\n' "$lock_dir"
}

deploy_write_state() {
  local path="$1"
  local value="$2"
  local temporary_file
  temporary_file="$(mktemp "${path}.tmp.XXXXXX")"
  printf '%s\n' "$value" >"$temporary_file"
  mv "$temporary_file" "$path"
}
