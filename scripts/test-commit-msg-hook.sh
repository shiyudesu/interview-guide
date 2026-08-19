#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$ROOT_DIR/.githooks/commit-msg"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if [[ ! -x "$HOOK" ]]; then
  echo "FAIL: commit-msg hook is missing or not executable: $HOOK" >&2
  exit 1
fi

assert_accepts() {
  local name=$1
  local message=$2
  local file="$TEMP_DIR/$name.txt"
  printf '%s\n' "$message" > "$file"
  if ! "$HOOK" "$file" >/dev/null 2>&1; then
    echo "FAIL: expected commit message to pass: $name" >&2
    return 1
  fi
}

assert_rejects() {
  local name=$1
  local message=$2
  local file="$TEMP_DIR/$name.txt"
  printf '%s\n' "$message" > "$file"
  if "$HOOK" "$file" >/dev/null 2>&1; then
    echo "FAIL: expected commit message to fail: $name" >&2
    return 1
  fi
}

assert_accepts "english-subject" "feat: add interview question import"
assert_accepts "chinese-subject" "docs(migration): 更新迁移检查清单"
assert_accepts "scope-and-body" $'fix(api): preserve legacy response fields\n\nExplain the compatibility impact.\n\nRefs: #12'
assert_accepts "breaking-change" $'refactor(backend)!: replace the backend runtime\n\nBREAKING CHANGE: implementation runtime changed without changing the API.'
assert_accepts "git-trailer" $'test: add contract coverage\n\nAdd API and worker golden-master cases.\n\nSigned-off-by: Example <example@example.com>'
assert_accepts "generated-merge" "Merge branch 'main'"
assert_accepts "generated-revert" 'Revert "feat: add interview question import"'
assert_accepts "generated-fixup" "fixup! feat: add interview question import"
assert_accepts "generated-squash" "squash! feat: add interview question import"
assert_accepts "generated-amend" "amend! feat: add interview question import"

assert_rejects "unsupported-type" "feature: add interview question import"
assert_rejects "missing-summary" "feat: "
assert_rejects "missing-space" "feat:add interview question import"
assert_rejects "invalid-scope" "fix(api server): preserve response fields"
assert_rejects "missing-blank-line" $'feat: add interview question import\nExplain the compatibility impact.'

echo "PASS: commit-msg hook validation passed"
