#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

campus_env_file=".env.campus"
compose_project="interview-guide-campus"
knowledge_artifact=".artifacts/opentrek-campus-full-knowledge.md"
container_knowledge_file="/tmp/opentrek-campus-full-knowledge.md"

fail() {
  echo "$1" >&2
  exit 1
}

if [[ "${1:-}" != "--yes" || $# -ne 1 ]]; then
  fail "该命令会替换全部已映射账号的本地知识库文件；确认后请运行 ./scripts/sync-campus-kb.sh --yes"
fi

command -v docker >/dev/null 2>&1 || fail "未找到 Docker。"
command -v python3 >/dev/null 2>&1 || fail "未找到 Python 3。"
[[ -f "$campus_env_file" ]] || fail "缺少 .env.campus。"

compose=(
  docker compose
  --project-name "$compose_project"
  --env-file "$campus_env_file"
  -f docker-compose.yml
)

"${compose[@]}" ps --services --status running | grep -qx postgres \
  || fail "校园实例 PostgreSQL 未运行，请先执行 ./scripts/start-campus.sh。"

python3 tools/scripts/build_campus_knowledge.py \
  --root . \
  --output "$knowledge_artifact"

readarray -t mapping_values < <(
  CAMPUS_ENV_FILE="$campus_env_file" CAMPUS_KNOWLEDGE_FILE="$knowledge_artifact" \
    python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def env_value(path: Path, name: str) -> str:
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.lstrip().startswith(name + "="):
            continue
        value = raw.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    raise SystemExit(f"{path} 缺少 {name}")


env_file = Path(os.environ["CAMPUS_ENV_FILE"])
knowledge_file = Path(os.environ["CAMPUS_KNOWLEDGE_FILE"])
document = json.loads(env_value(env_file, "APP_OPENTREK_KB_MAPPINGS_JSON") or "[]")
if isinstance(document, dict):
    mappings = {str(key).lower(): str(value) for key, value in document.items()}
elif isinstance(document, list):
    mappings = {
        str(item.get("fileHash") or "").lower(): str(item.get("kbCode") or "")
        for item in document
        if isinstance(item, dict)
    }
else:
    raise SystemExit("APP_OPENTREK_KB_MAPPINGS_JSON 必须是数组或对象")
for file_hash, kb_code in mappings.items():
    if len(file_hash) != 64 or any(character not in "0123456789abcdef" for character in file_hash):
        raise SystemExit("APP_OPENTREK_KB_MAPPINGS_JSON 包含无效 SHA-256")
    if not kb_code:
        raise SystemExit("APP_OPENTREK_KB_MAPPINGS_JSON 包含空 kbCode")
kb_codes = set(mappings.values())
if len(kb_codes) != 1:
    raise SystemExit(
        "自动同步要求 APP_OPENTREK_KB_MAPPINGS_JSON 只映射一个 Kortex kbCode"
    )
new_hash = hashlib.sha256(knowledge_file.read_bytes()).hexdigest()
print(next(iter(kb_codes)))
print(new_hash)
for value in sorted(mappings):
    print(value)
PY
)

[[ ${#mapping_values[@]} -ge 3 ]] || fail "无法解析 Kortex 映射。"
kb_code="${mapping_values[0]}"
knowledge_hash="${mapping_values[1]}"
mapped_hashes=("${mapping_values[@]:2}")

sql_hashes=""
for file_hash in "${mapped_hashes[@]}"; do
  [[ "$file_hash" =~ ^[0-9a-f]{64}$ ]] || fail "Kortex 映射包含无效 SHA-256。"
  [[ -z "$sql_hashes" ]] || sql_hashes+=","
  sql_hashes+="'$file_hash'"
done

preflight_rows="$(
  "${compose[@]}" exec -T postgres sh -lc \
    "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -X -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -F '|' -c \"SELECT u.email, count(DISTINCT kb.id), count(q.id) FROM knowledge_bases kb JOIN users u ON u.id = kb.user_id LEFT JOIN knowledge_base_questions q ON q.knowledge_base_id = kb.id WHERE kb.file_hash IN ($sql_hashes) AND u.kind = 'HUMAN' AND u.status = 'ACTIVE' GROUP BY u.email ORDER BY u.email;\""
)"
[[ -n "$preflight_rows" ]] || fail "没有找到需要同步的已激活知识库影子账号。"

sync_users=()
while IFS='|' read -r user_email shadow_count generated_count; do
  [[ "$shadow_count" == "1" ]] \
    || fail "账号 ${user_email} 在目标 kbCode 下有 ${shadow_count} 个影子记录，拒绝自动替换。"
  [[ "$generated_count" == "0" ]] \
    || fail "账号 ${user_email} 已有 ${generated_count} 道题目，拒绝自动替换。"
  sync_users+=("$user_email")
done <<<"$preflight_rows"

CAMPUS_ENV_FILE="$campus_env_file" CAMPUS_KB_CODE="$kb_code" \
  CAMPUS_KNOWLEDGE_HASH="$knowledge_hash" python3 - <<'PY'
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


path = Path(os.environ["CAMPUS_ENV_FILE"])
kb_code = os.environ["CAMPUS_KB_CODE"]
file_hash = os.environ["CAMPUS_KNOWLEDGE_HASH"]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
found: int | None = None
mappings: dict[str, str] = {}
for index, line in enumerate(lines):
    if not line.lstrip().startswith("APP_OPENTREK_KB_MAPPINGS_JSON="):
        continue
    found = index
    raw = line.split("=", 1)[1].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    document = json.loads(raw or "[]")
    if isinstance(document, dict):
        mappings = {str(key).lower(): str(value) for key, value in document.items()}
    elif isinstance(document, list):
        mappings = {
            str(item.get("fileHash") or "").lower(): str(item.get("kbCode") or "")
            for item in document
            if isinstance(item, dict)
        }
    else:
        raise SystemExit("APP_OPENTREK_KB_MAPPINGS_JSON 必须是数组或对象")
    break
if found is None:
    raise SystemExit(".env.campus 缺少 APP_OPENTREK_KB_MAPPINGS_JSON")
existing = mappings.get(file_hash)
if existing not in {None, kb_code}:
    raise SystemExit(f"完整文件哈希已映射到其他 kbCode: {existing}")
mappings[file_hash] = kb_code
rendered = json.dumps(
    [{"fileHash": key, "kbCode": value} for key, value in sorted(mappings.items())],
    ensure_ascii=False,
    separators=(",", ":"),
)
ending = "\r\n" if lines[found].endswith("\r\n") else "\n"
lines[found] = f"APP_OPENTREK_KB_MAPPINGS_JSON='{rendered}'{ending}"
descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
temporary = Path(temporary_name)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(lines))
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, path.stat().st_mode & 0o777)
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
PY

./scripts/start-campus.sh

"${compose[@]}" cp "$knowledge_artifact" "app:$container_knowledge_file"

for user_email in "${sync_users[@]}"; do
  "${compose[@]}" exec -T app interview-guide-seed-opentrek-kb \
    --user-email "$user_email" \
    --file "$container_knowledge_file" \
    --kb-code "$kb_code" \
    --name "OpenTrek 校园技术资料" \
    --replace-existing \
    --skip-env-update
done

"${compose[@]}" exec -T postgres sh -lc \
  "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -X -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -P pager=off -c \"SELECT u.email, kb.original_filename, kb.file_size FROM knowledge_bases kb JOIN users u ON u.id = kb.user_id WHERE kb.file_hash = '$knowledge_hash' ORDER BY u.email;\""

echo "校园知识库同步完成：账号数 ${#sync_users[@]}，文件哈希 ${knowledge_hash}。"
