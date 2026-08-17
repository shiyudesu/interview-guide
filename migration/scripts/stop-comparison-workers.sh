#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

runtime_dir="$comparison_runtime/question-workers"
for pid_file in \
  "$runtime_dir/python/worker.pid" \
  "$runtime_dir/java/worker.pid"; do
  if [[ ! -f "$pid_file" ]]; then
    continue
  fi
  pid="$(cat "$pid_file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in $(seq 1 30); do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
  fi
  rm -f "$pid_file"
done

echo "Comparison workers stopped"
