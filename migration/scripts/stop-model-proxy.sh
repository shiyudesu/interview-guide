#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"
stop_pid_file "$comparison_runtime/model-proxy/proxy.pid"
