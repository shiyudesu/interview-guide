#!/usr/bin/env python3
"""Generate deterministic repository inventories from source files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
REDIS_CONSTANT_MARKERS = (
    "STREAM",
    "GROUP",
    "CONSUMER",
    "FIELD",
    "RETRY",
    "BATCH",
    "PENDING",
    "POLL",
    "CACHE",
    "LOCK",
    "KEY",
    "TTL",
)


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=repository_root)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def source_line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_path(path: str) -> str:
    normalized = re.sub(r"^(?:https?|wss?)://[^/]+", "", path)
    normalized = re.sub(r"\$\{(?:query|queryString|searchParams)\b.*$", "", normalized)
    normalized = re.sub(r"\$\{[^}]+\}", "{}", normalized.split("?", 1)[0])
    normalized = re.sub(r"\{[^}]+\}", "{}", normalized)
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.rstrip("/") or "/"


def join_paths(prefix: str, suffix: str) -> str:
    if not prefix:
        return suffix or "/"
    if not suffix:
        return prefix
    return f"{prefix.rstrip('/')}/{suffix.lstrip('/')}"


def extract_python_api(root: Path) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for path in sorted((root / "backend/src/interview_guide").glob("**/*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        prefix = ""
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "router" for target in node.targets
            ):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            for keyword in node.value.keywords:
                if (
                    keyword.arg == "prefix"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    prefix = keyword.value.value
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(
                    decorator.func, ast.Attribute
                ):
                    continue
                owner = decorator.func.value
                if not isinstance(owner, ast.Name) or owner.id not in {"router", "app"}:
                    continue
                method = decorator.func.attr.lower()
                if method not in {"get", "post", "put", "patch", "delete", "websocket"}:
                    continue
                suffix = ""
                if (
                    decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    suffix = decorator.args[0].value
                path_value = join_paths(prefix if owner.id == "router" else "", suffix)
                transport = "websocket" if method == "websocket" else "rest"
                if any(
                    isinstance(candidate, ast.Call)
                    and (
                        (
                            isinstance(candidate.func, ast.Name)
                            and candidate.func.id == "StreamingResponse"
                        )
                        or (
                            isinstance(candidate.func, ast.Attribute)
                            and candidate.func.attr == "StreamingResponse"
                        )
                    )
                    for candidate in ast.walk(node)
                ):
                    transport = "sse"
                endpoints.append(
                    {
                        "canonicalPath": canonical_path(path_value),
                        "consumes": None,
                        "controller": path.stem,
                        "frontendUsages": [],
                        "handler": node.name,
                        "httpMethod": "WEBSOCKET" if method == "websocket" else method.upper(),
                        "parameters": [
                            {
                                "name": argument.arg,
                                "annotation": ast.unparse(argument.annotation)
                                if argument.annotation is not None
                                else None,
                            }
                            for argument in node.args.args
                        ],
                        "path": path_value,
                        "produces": "text/event-stream" if transport == "sse" else None,
                        "source": {
                            "file": relative(root, path),
                            "line": decorator.lineno,
                        },
                        "transport": transport,
                    }
                )
    return sorted(
        endpoints,
        key=lambda item: (
            item["path"],
            item["httpMethod"],
            item["controller"],
            item["handler"],
        ),
    )


def infer_frontend_method(text: str, offset: int) -> str:
    context = text[max(0, offset - 500) : offset]
    request_methods = re.findall(r"request\.(get|post|put|patch|delete|upload|download)\b", context)
    if request_methods:
        method = request_methods[-1]
        return {"upload": "POST", "download": "GET"}.get(method, method.upper())
    explicit = re.findall(r"\bmethod\s*:\s*['\"]([A-Z]+)['\"]", context)
    return explicit[-1] if explicit else "UNKNOWN"


def extract_frontend_api(root: Path) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    literal_pattern = re.compile(
        r"(?P<quote>['\"`])"
        r"(?P<path>(?:(?:https?|wss?)://[^/'\"`]+)?/(?:api|ws)/.*?)"
        r"(?P=quote)"
    )
    for path in sorted((root / "frontend/src").glob("**/*.[tT][sS]*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        for match in literal_pattern.finditer(text):
            raw_path = match.group("path")
            if "://" in raw_path:
                hostname = urlsplit(raw_path).hostname
                if hostname not in {"localhost", "127.0.0.1"}:
                    continue
            calls.append(
                {
                    "canonicalPath": canonical_path(raw_path),
                    "httpMethod": infer_frontend_method(text, match.start()),
                    "path": raw_path,
                    "source": {
                        "file": relative(root, path),
                        "line": source_line(text, match.start()),
                    },
                }
            )
    unique = {
        (
            call["path"],
            call["httpMethod"],
            call["source"]["file"],
            call["source"]["line"],
        ): call
        for call in calls
    }
    return sorted(
        unique.values(),
        key=lambda item: (
            item["path"],
            item["httpMethod"],
            item["source"]["file"],
            item["source"]["line"],
        ),
    )


def build_api_manifest(root: Path) -> dict[str, Any]:
    endpoints = extract_python_api(root)
    frontend_calls = extract_frontend_api(root)
    calls_by_path: dict[str, list[dict[str, Any]]] = {}
    for call in frontend_calls:
        calls_by_path.setdefault(call["canonicalPath"], []).append(call)
    backend_paths = {endpoint["canonicalPath"] for endpoint in endpoints}
    for endpoint in endpoints:
        endpoint["frontendUsages"] = calls_by_path.get(endpoint["canonicalPath"], [])
    frontend_only = [call for call in frontend_calls if call["canonicalPath"] not in backend_paths]
    backend_only = [
        {
            "httpMethod": endpoint["httpMethod"],
            "path": endpoint["path"],
            "source": endpoint["source"],
        }
        for endpoint in endpoints
        if not endpoint["frontendUsages"]
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceOfTruth": [
            "FastAPI route decorators",
            "frontend/src URL literals",
        ],
        "summary": {
            "backendEndpointCount": len(endpoints),
            "backendOnlyCount": len(backend_only),
            "controllerCount": len({item["controller"] for item in endpoints}),
            "frontendCallCount": len(frontend_calls),
            "frontendOnlyCount": len(frontend_only),
            "sseEndpointCount": sum(item["transport"] == "sse" for item in endpoints),
            "webSocketEndpointCount": sum(item["transport"] == "websocket" for item in endpoints),
        },
        "backendEndpoints": endpoints,
        "frontendCalls": frontend_calls,
        "unmatched": {
            "backendOnly": backend_only,
            "frontendOnly": frontend_only,
        },
    }


def matching_parenthesis(text: str, opening: int) -> int:
    depth = 0
    quote: str | None = None
    for index in range(opening, len(text)):
        character = text[index]
        if quote:
            if character == quote and text[index - 1] != "\\":
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_definitions(body: str) -> list[str]:
    definitions: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for index, character in enumerate(body):
        if quote:
            if character == quote and body[index - 1] != "\\":
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            definitions.append(compact(body[start:index]))
            start = index + 1
    tail = compact(body[start:])
    if tail:
        definitions.append(tail)
    return definitions


def extract_database(root: Path) -> dict[str, Any]:
    migrations: list[dict[str, Any]] = []
    extensions: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    indexes: list[dict[str, Any]] = []
    alterations: list[dict[str, Any]] = []
    sql_paths = sorted((root / "backend/alembic/sql").glob("*.sql"))
    revision_paths = sorted((root / "backend/alembic/versions").glob("*.py"))
    dropped_tables: set[str] = set()
    dropped_columns: dict[str, set[str]] = {}
    added_columns: dict[str, list[dict[str, str]]] = {}
    for path in [*sql_paths, *revision_paths]:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            upgrade_start = text.find("def upgrade()")
            downgrade_start = text.find("def downgrade()")
            if upgrade_start < 0:
                continue
            text = text[upgrade_start : downgrade_start if downgrade_start >= 0 else None]
        source = relative(root, path)
        migrations.append(
            {
                "file": source,
                "sha256": sha256(path),
                "statementTerminatorCount": text.count(";"),
            }
        )
        for match in re.finditer(
            r"CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+"
            r"(?:\"([^\"]+)\"|([\w-]+))",
            text,
            flags=re.IGNORECASE,
        ):
            extensions.append(
                {
                    "name": match.group(1) or match.group(2),
                    "source": {"file": source, "line": source_line(text, match.start())},
                }
            )
        table_pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"(?:public\.)?(?:\"([^\"]+)\"|(\w+))\s*\(",
            flags=re.IGNORECASE,
        )
        for match in table_pattern.finditer(text):
            close = matching_parenthesis(text, match.end() - 1)
            if close < 0:
                continue
            definitions = split_definitions(text[match.end() : close])
            columns: list[dict[str, str]] = []
            constraints: list[str] = []
            for definition in definitions:
                if re.match(
                    r"^(?:CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|"
                    r"UNIQUE|CHECK)\b",
                    definition,
                    flags=re.IGNORECASE,
                ):
                    constraints.append(definition)
                    continue
                column_match = re.match(r'(?:"([^"]+)"|(\w+))\s+(.+)', definition)
                if column_match:
                    columns.append(
                        {
                            "definition": compact(column_match.group(3)),
                            "name": column_match.group(1) or column_match.group(2),
                        }
                    )
            tables.append(
                {
                    "columns": columns,
                    "constraints": constraints,
                    "name": match.group(1) or match.group(2),
                    "source": {"file": source, "line": source_line(text, match.start())},
                }
            )
        for match in re.finditer(
            r"CREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"(?:\"([^\"]+)\"|(\w+))\s+ON\s+(.+?);",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            indexes.append(
                {
                    "definition": compact(match.group(0)),
                    "name": match.group(2) or match.group(3),
                    "source": {"file": source, "line": source_line(text, match.start())},
                    "unique": bool(match.group(1)),
                }
            )
        for match in re.finditer(
            r"ALTER\s+TABLE\s+.+?;",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            alterations.append(
                {
                    "definition": compact(match.group(0)),
                    "source": {"file": source, "line": source_line(text, match.start())},
                }
            )
        for match in re.finditer(
            r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\"([^\"]+)\"|(\w+))",
            text,
            flags=re.IGNORECASE,
        ):
            dropped_tables.add(match.group(1) or match.group(2))
        for match in re.finditer(
            r"ALTER\s+TABLE\s+(?:\"([^\"]+)\"|(\w+))(?P<body>.+?);",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            table_name = match.group(1) or match.group(2)
            for definition in split_definitions(match.group("body")):
                column = re.match(
                    r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                    r'(?:"([^"]+)"|(\w+))\s+(.+)',
                    definition,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if column is not None:
                    added_columns.setdefault(table_name, []).append(
                        {
                            "definition": compact(column.group(3)),
                            "name": column.group(1) or column.group(2),
                        }
                    )
            for column in re.finditer(
                r"DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?(?:\"([^\"]+)\"|(\w+))",
                match.group("body"),
                flags=re.IGNORECASE,
            ):
                dropped_columns.setdefault(table_name, set()).add(
                    column.group(1) or column.group(2)
                )
    tables = [table for table in tables if table["name"] not in dropped_tables]
    for table in tables:
        removed = dropped_columns.get(table["name"], set())
        table["columns"] = [
            column for column in table["columns"] if column["name"] not in removed
        ]
        existing_columns = {column["name"] for column in table["columns"]}
        table["columns"].extend(
            column
            for column in added_columns.get(table["name"], [])
            if column["name"] not in existing_columns and column["name"] not in removed
        )
    live_table_names = {table["name"] for table in tables}
    indexes = [
        index
        for index in indexes
        if not any(
            re.search(rf"\bON\s+(?:public\.)?\"?{re.escape(table)}\"?\b", index["definition"], re.I)
            for table in dropped_tables
            if table not in live_table_names
        )
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceOfTruth": "Alembic accepted production SQL and PostgreSQL catalog tests.",
        "summary": {
            "alterationCount": len(alterations),
            "extensionCount": len(extensions),
            "indexCount": len(indexes),
            "migrationCount": len(migrations),
            "tableCount": len(tables),
        },
        "migrations": migrations,
        "extensions": extensions,
        "tables": tables,
        "indexes": indexes,
        "alterations": alterations,
    }


def extract_redis(root: Path) -> dict[str, Any]:
    python_root = root / "backend/src/interview_guide"
    constants: list[dict[str, Any]] = []
    scheduled: list[dict[str, Any]] = []
    rate_limits: list[dict[str, Any]] = []
    key_literals: list[dict[str, Any]] = []
    operation_evidence: list[dict[str, Any]] = []
    stream_count = 0
    for path in sorted(python_root.glob("**/*.py")):
        text = path.read_text(encoding="utf-8")
        source = relative(root, path)
        for match in re.finditer(
            r"(?m)^([A-Z][A-Z0-9_]*)\s*(?::[^=]+)?=\s*(.+)$",
            text,
        ):
            name = match.group(1)
            if any(marker in name for marker in REDIS_CONSTANT_MARKERS):
                constants.append(
                    {
                        "name": name,
                        "source": {
                            "file": source,
                            "line": source_line(text, match.start()),
                        },
                        "valueExpression": compact(match.group(2)),
                    }
                )
        stream_count += len(re.findall(r"(?m)^[A-Z][A-Z0-9_]*\s*=\s*StreamDefinition\(", text))
        for match in re.finditer(
            r"scheduler\.add_job\(\s*(\w+).*?trigger=\"([^\"]+)\"",
            text,
            re.DOTALL,
        ):
            scheduled.append(
                {
                    "method": match.group(1),
                    "schedule": match.group(2),
                    "source": {
                        "file": source,
                        "line": source_line(text, match.start()),
                    },
                }
            )
        for match in re.finditer(r"\.rate_limiter\.check\((.*?)\n\s*\)", text, flags=re.DOTALL):
            rate_limits.append(
                {
                    "arguments": compact(match.group(1)),
                    "method": None,
                    "source": {
                        "file": source,
                        "line": source_line(text, match.start()),
                    },
                }
            )
        if re.search(r"redis|xreadgroup|xautoclaim|xadd|xack", text, re.IGNORECASE):
            for match in re.finditer(r'"([^"\n]+:[^"\n]+)"', text):
                value = match.group(1)
                if "://" in value or " " in value:
                    continue
                key_literals.append(
                    {
                        "source": {
                            "file": source,
                            "line": source_line(text, match.start()),
                        },
                        "value": value,
                    }
                )
            for line_number, line in enumerate(text.splitlines(), start=1):
                if re.search(
                    r"\b(?:xadd|xack|xreadgroup|xautoclaim|evalsha|script_load)\b",
                    line,
                    re.IGNORECASE,
                ):
                    operation_evidence.append(
                        {
                            "code": compact(line),
                            "source": {"file": source, "line": line_number},
                        }
                    )
    lua_paths = sorted((root / "backend/resources/scripts").glob("*.lua"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "constantCount": len(constants),
            "rateLimitRuleCount": len(rate_limits),
            "scheduledMethodCount": len(scheduled),
            "streamCount": stream_count,
        },
        "constants": constants,
        "keyLiterals": key_literals,
        "luaScripts": [
            {"file": relative(root, path), "sha256": sha256(path)} for path in lua_paths
        ],
        "operationEvidence": operation_evidence,
        "rateLimits": rate_limits,
        "scheduledMethods": scheduled,
    }


def yaml_values(root: Path, path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith(("#", "-")):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(?:\s*(.*))?$", line)
        if not match:
            continue
        indent = len(match.group(1).replace("\t", "    "))
        key = match.group(2)
        raw_value = (match.group(3) or "").strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        property_path = ".".join([item[1] for item in stack] + [key])
        if raw_value and raw_value not in {"|", ">"}:
            env_references = [
                {
                    "default": env_match.group(2) if env_match.group(2) is not None else None,
                    "name": env_match.group(1),
                    "sensitive": bool(
                        re.search(
                            r"(?:KEY|PASSWORD|SECRET|TOKEN|CREDENTIAL)",
                            env_match.group(1),
                        )
                    ),
                }
                for env_match in re.finditer(r"\$\{([A-Za-z0-9_.-]+)(?::([^}]*))?\}", raw_value)
            ]
            values.append(
                {
                    "environmentReferences": env_references,
                    "property": property_path,
                    "rawValue": raw_value,
                    "source": {
                        "file": relative(root, path),
                        "line": line_number,
                    },
                }
            )
        else:
            stack.append((indent, key))
    return values


def extract_configuration(root: Path) -> dict[str, Any]:
    yaml_paths = [root / "docker-compose.dev.yml", root / "docker-compose.yml"]
    values = [value for path in yaml_paths if path.exists() for value in yaml_values(root, path)]
    env_example: list[dict[str, Any]] = []
    env_path = root / ".env.example"
    for line_number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            env_example.append(
                {
                    "default": match.group(2),
                    "name": match.group(1),
                    "sensitive": bool(
                        re.search(
                            r"(?:KEY|PASSWORD|SECRET|TOKEN|CREDENTIAL)",
                            match.group(1),
                        )
                    ),
                    "source": {
                        "file": relative(root, env_path),
                        "line": line_number,
                    },
                }
            )
    property_bindings: list[dict[str, Any]] = []
    value_injections: list[dict[str, Any]] = []
    for path in sorted((root / "backend/src/interview_guide").glob("**/*.py")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"(?m)^\s*(\w+):[^=]+?=\s*Field\((.*?)validation_alias=\"([A-Z0-9_]+)\"",
            text,
            re.DOTALL,
        ):
            property_bindings.append(
                {
                    "field": match.group(1),
                    "environment": match.group(3),
                    "source": {
                        "file": relative(root, path),
                        "line": source_line(text, match.start()),
                    },
                }
            )
    env_names = {
        reference["name"] for value in values for reference in value["environmentReferences"]
    }
    example_names = {item["name"] for item in env_example}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "configurationValueCount": len(values),
            "envExampleCount": len(env_example),
            "envReferencedButUndocumentedCount": len(env_names - example_names),
            "propertyBindingCount": len(property_bindings),
        },
        "configurationValues": values,
        "envExample": env_example,
        "envReferencedButUndocumented": sorted(env_names - example_names),
        "propertyBindings": property_bindings,
        "valueInjections": value_injections,
    }


def resource_entry(root: Path, path: Path, category: str) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "category": category,
        "file": relative(root, path),
        "sha256": sha256(path),
    }


def extract_resources(root: Path) -> dict[str, Any]:
    resource_root = root / "backend/resources"
    patterns = {
        "font": "fonts/**/*",
        "prompt": "prompts/**/*",
        "redis-script": "scripts/**/*",
        "skill": "skills/**/*",
    }
    resources: list[dict[str, Any]] = []
    for category, pattern in patterns.items():
        for path in sorted(resource_root.glob(pattern)):
            if path.is_file():
                resources.append(resource_entry(root, path, category))
    tests: list[dict[str, Any]] = []
    test_roots = [
        root / "backend/tests",
        root / "frontend/e2e",
        root / "frontend/src",
    ]
    for test_root in test_roots:
        if not test_root.exists():
            continue
        for path in sorted(test_root.glob("**/*")):
            if not path.is_file():
                continue
            if not (
                path.suffix in {".py", ".ts", ".tsx"}
                and ("test" in path.name.lower() or "spec" in path.name.lower())
            ):
                continue
            text = path.read_text(encoding="utf-8")
            tests.append(
                {
                    "disabledMarkers": len(re.findall(r"@Disabled\b|\.skip\(", text)),
                    "file": relative(root, path),
                    "sha256": sha256(path),
                }
            )
    category_counts = Counter(item["category"] for item in resources)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "disabledTestMarkerCount": sum(item["disabledMarkers"] for item in tests),
            "resourceCount": len(resources),
            "resourceCountsByCategory": dict(sorted(category_counts.items())),
            "testFileCount": len(tests),
        },
        "resources": resources,
        "tests": tests,
    }


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = (args.output or root / "tools/manifests").resolve()
    manifests = {
        "api.json": build_api_manifest(root),
        "configuration.json": extract_configuration(root),
        "database.json": extract_database(root),
        "redis.json": extract_redis(root),
        "resources.json": extract_resources(root),
    }
    for name, value in manifests.items():
        write_json(output, name, value)
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "manifests": {name: value["summary"] for name, value in sorted(manifests.items())},
        "maintenance": [
            "Keep production Compose, Python tests, repository manifests, "
            "and protected model checks green.",
        ],
    }
    write_json(output, "summary.json", summary)


if __name__ == "__main__":
    main()
