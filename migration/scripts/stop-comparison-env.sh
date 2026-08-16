#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

stop_pid_file "$comparison_runtime/java/app.pid"
stop_pid_file "$comparison_runtime/candidate/app.pid"

if [[ "${1:-}" == "--purge" ]]; then
  compose down --volumes --remove-orphans
else
  compose down --remove-orphans
fi
