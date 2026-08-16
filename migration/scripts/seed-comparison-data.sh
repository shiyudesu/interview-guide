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

python3 "$repo_root/migration/scripts/runtime_state.py" seed-s3 \
  --s3-endpoint http://127.0.0.1:19000 \
  --s3-access-key comparison-access \
  --s3-secret-key comparison-secret \
  --s3-bucket interview-guide-java \
  --key comparison/baseline.txt \
  --content 'deterministic migration comparison object'
python3 "$repo_root/migration/scripts/runtime_state.py" seed-s3 \
  --s3-endpoint http://127.0.0.1:19000 \
  --s3-access-key comparison-access \
  --s3-secret-key comparison-secret \
  --s3-bucket interview-guide-python \
  --key comparison/baseline.txt \
  --content 'deterministic migration comparison object'
