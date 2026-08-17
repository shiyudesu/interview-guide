#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

(
  cd "$repo_root/backend"
  uv run --frozen python ../migration/scripts/rag_chat_comparison.py
)
