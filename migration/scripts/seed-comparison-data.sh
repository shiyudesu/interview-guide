#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/comparison-common.sh"

seed_file="$repo_root/migration/samples/database/seed.sql"
compose exec -T java-postgres \
  psql \
  --set ON_ERROR_STOP=1 \
  --username postgres \
  --dbname interview_guide_java \
  <"$seed_file"
compose exec -T python-postgres \
  psql \
  --set ON_ERROR_STOP=1 \
  --username postgres \
  --dbname interview_guide_python \
  <"$seed_file"
