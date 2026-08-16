#!/usr/bin/env python3
"""Generate deterministic Stage 0 migration inventories from repository sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MAPPING_METHODS = {
    "GetMapping": ["GET"],
    "PostMapping": ["POST"],
    "PutMapping": ["PUT"],
    "PatchMapping": ["PATCH"],
    "DeleteMapping": ["DELETE"],
}
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
    normalized = re.sub(
        r"\$\{(?:query|queryString|searchParams)\b.*$", "", normalized
    )
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


def annotation_blocks(lines: list[str]) -> list[tuple[int, int, str, str]]:
    blocks: list[tuple[int, int, str, str]] = []
    mapping_pattern = re.compile(
        r"^\s*@(GetMapping|PostMapping|PutMapping|PatchMapping|"
        r"DeleteMapping|RequestMapping)\b"
    )
    index = 0
    while index < len(lines):
        match = mapping_pattern.match(lines[index])
        if not match:
            index += 1
            continue
        start = index
        text = lines[index].strip()
        balance = text.count("(") - text.count(")")
        while balance > 0 and index + 1 < len(lines):
            index += 1
            next_line = lines[index].strip()
            text += " " + next_line
            balance += next_line.count("(") - next_line.count(")")
        blocks.append((start, index, match.group(1), compact(text)))
        index += 1
    return blocks


def annotation_path(annotation: str) -> str:
    named = re.search(r"\b(?:value|path)\s*=\s*\"([^\"]*)\"", annotation)
    if named:
        return named.group(1)
    positional = re.search(r"@\w+Mapping\s*\(\s*\"([^\"]*)\"", annotation)
    return positional.group(1) if positional else ""


def annotation_http_methods(kind: str, annotation: str) -> list[str]:
    if kind in MAPPING_METHODS:
        return MAPPING_METHODS[kind]
    methods = re.findall(r"RequestMethod\.([A-Z]+)", annotation)
    return methods or ["ANY"]


def find_method_signature(
    lines: list[str], annotation_end: int
) -> tuple[str, str] | None:
    candidate = "\n".join(lines[annotation_end + 1 : annotation_end + 35])
    match = re.search(
        r"\b(?:public|protected|private)\s+"
        r"[\w<>, ?.\[\]]+\s+(\w+)\s*\((.*?)\)\s*\{",
        candidate,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return match.group(1), compact(match.group(2))


def extract_java_api(root: Path) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    controller_paths = sorted(
        (root / "app/src/main/java").glob("**/*Controller.java")
    )
    for path in controller_paths:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        class_match = re.search(r"\bpublic\s+class\s+(\w+)", text)
        if not class_match:
            continue
        class_name = class_match.group(1)
        class_line = source_line(text, class_match.start()) - 1
        blocks = annotation_blocks(lines)
        class_prefix = ""
        for start, _, kind, annotation in blocks:
            if start >= class_line:
                break
            if kind == "RequestMapping":
                class_prefix = annotation_path(annotation)

        for start, end, kind, annotation in blocks:
            if start < class_line:
                continue
            signature = find_method_signature(lines, end)
            if not signature:
                continue
            method_name, parameters = signature
            path_value = join_paths(class_prefix, annotation_path(annotation))
            consumes_match = re.search(r"\bconsumes\s*=\s*([^,)]+)", annotation)
            produces_match = re.search(r"\bproduces\s*=\s*([^,)]+)", annotation)
            parameter_annotations = [
                {
                    "kind": match.group(1),
                    "arguments": compact(match.group(2) or ""),
                }
                for match in re.finditer(
                    r"@(RequestParam|PathVariable|RequestBody|RequestPart)"
                    r"\s*(\([^)]*\))?",
                    parameters,
                )
            ]
            for http_method in annotation_http_methods(kind, annotation):
                endpoints.append(
                    {
                        "canonicalPath": canonical_path(path_value),
                        "consumes": compact(consumes_match.group(1))
                        if consumes_match
                        else None,
                        "controller": class_name,
                        "frontendUsages": [],
                        "httpMethod": http_method,
                        "javaMethod": method_name,
                        "parameters": parameter_annotations,
                        "path": path_value,
                        "produces": compact(produces_match.group(1))
                        if produces_match
                        else None,
                        "source": {
                            "file": relative(root, path),
                            "line": start + 1,
                        },
                        "transport": "sse"
                        if "TEXT_EVENT_STREAM" in annotation
                        else "rest",
                        "usesValid": "@Valid" in parameters,
                    }
                )

    websocket_config = root / (
        "app/src/main/java/interview/guide/modules/voiceinterview/"
        "config/WebSocketConfig.java"
    )
    if websocket_config.exists():
        text = websocket_config.read_text(encoding="utf-8")
        for match in re.finditer(r"\.addHandler\([^,]+,\s*\"([^\"]+)\"\)", text):
            path_value = match.group(1)
            endpoints.append(
                {
                    "canonicalPath": canonical_path(path_value),
                    "consumes": "text/json",
                    "controller": "VoiceInterviewWebSocketHandler",
                    "frontendUsages": [],
                    "httpMethod": "WEBSOCKET",
                    "javaMethod": "handleTextMessage",
                    "parameters": [],
                    "path": path_value,
                    "produces": "text/json",
                    "source": {
                        "file": relative(root, websocket_config),
                        "line": source_line(text, match.start()),
                    },
                    "transport": "websocket",
                    "usesValid": False,
                }
            )
    return sorted(
        endpoints,
        key=lambda item: (
            item["path"],
            item["httpMethod"],
            item["controller"],
            item["javaMethod"],
        ),
    )


def infer_frontend_method(text: str, offset: int) -> str:
    context = text[max(0, offset - 500) : offset]
    request_methods = re.findall(
        r"request\.(get|post|put|patch|delete|upload|download)\b", context
    )
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
    endpoints = extract_java_api(root)
    frontend_calls = extract_frontend_api(root)
    calls_by_path: dict[str, list[dict[str, Any]]] = {}
    for call in frontend_calls:
        calls_by_path.setdefault(call["canonicalPath"], []).append(call)
    backend_paths = {endpoint["canonicalPath"] for endpoint in endpoints}
    for endpoint in endpoints:
        endpoint["frontendUsages"] = calls_by_path.get(endpoint["canonicalPath"], [])
    frontend_only = [
        call for call in frontend_calls if call["canonicalPath"] not in backend_paths
    ]
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
            "Java controller mappings",
            "Java WebSocket registration",
            "frontend/src URL literals",
        ],
        "summary": {
            "backendEndpointCount": len(endpoints),
            "backendOnlyCount": len(backend_only),
            "controllerCount": len({item["controller"] for item in endpoints}),
            "frontendCallCount": len(frontend_calls),
            "frontendOnlyCount": len(frontend_only),
            "sseEndpointCount": sum(
                item["transport"] == "sse" for item in endpoints
            ),
            "webSocketEndpointCount": sum(
                item["transport"] == "websocket" for item in endpoints
            ),
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
    sql_paths = sorted((root / "app/src/main/resources/db/migration").glob("*.sql"))
    for path in sql_paths:
        text = path.read_text(encoding="utf-8")
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
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceOfTruth": "Flyway SQL; PostgreSQL catalog comparison is added in Stage 1/3.",
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
    java_root = root / "app/src/main/java"
    constants: list[dict[str, Any]] = []
    scheduled: list[dict[str, Any]] = []
    rate_limits: list[dict[str, Any]] = []
    key_literals: list[dict[str, Any]] = []
    operation_evidence: list[dict[str, Any]] = []
    for path in sorted(java_root.glob("**/*.java")):
        text = path.read_text(encoding="utf-8")
        source = relative(root, path)
        for match in re.finditer(
            r"\bstatic\s+final\s+[\w<>, ?.\[\]]+\s+(\w+)\s*=\s*(.*?);",
            text,
            flags=re.DOTALL,
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
        for match in re.finditer(
            r"@Scheduled\s*\((.*?)\)\s*"
            r"(?:public|protected|private)\s+[\w<>, ?.\[\]]+\s+(\w+)\s*\(",
            text,
            flags=re.DOTALL,
        ):
            scheduled.append(
                {
                    "method": match.group(2),
                    "schedule": compact(match.group(1)),
                    "source": {
                        "file": source,
                        "line": source_line(text, match.start()),
                    },
                }
            )
        for match in re.finditer(r"@RateLimit\s*\((.*?)\)", text, flags=re.DOTALL):
            following = text[match.end() : match.end() + 1200]
            method_match = re.search(
                r"(?:public|protected|private)\s+[\w<>, ?.\[\]]+\s+(\w+)\s*\(",
                following,
            )
            rate_limits.append(
                {
                    "arguments": compact(match.group(1)),
                    "method": method_match.group(1) if method_match else None,
                    "source": {
                        "file": source,
                        "line": source_line(text, match.start()),
                    },
                }
            )
        if re.search(r"redis|redisson|RStream|RLock|RBucket|RMap", text, re.IGNORECASE):
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
                    r"\b(?:getBucket|getMap|getLock|getStream|stream[A-Z]\w*|"
                    r"RScript|evalSha|scriptLoad)\b",
                    line,
                ):
                    operation_evidence.append(
                        {
                            "code": compact(line),
                            "source": {"file": source, "line": line_number},
                        }
                    )
    lua_paths = sorted((root / "app/src/main/resources/scripts").glob("*.lua"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "constantCount": len(constants),
            "rateLimitRuleCount": len(rate_limits),
            "scheduledMethodCount": len(scheduled),
            "streamCount": sum(item["name"].endswith("STREAM_KEY") for item in constants),
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
                for env_match in re.finditer(
                    r"\$\{([A-Za-z0-9_.-]+)(?::([^}]*))?\}", raw_value
                )
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
    yaml_paths = sorted((root / "app/src/main/resources").glob("*.yml"))
    yaml_paths += [root / "docker-compose.dev.yml", root / "docker-compose.yml"]
    values = [
        value
        for path in yaml_paths
        if path.exists()
        for value in yaml_values(root, path)
    ]
    env_example: list[dict[str, Any]] = []
    env_path = root / ".env.example"
    for line_number, line in enumerate(
        env_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
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
    for path in sorted((root / "app/src/main/java").glob("**/*.java")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"@ConfigurationProperties\s*\(\s*prefix\s*=\s*\"([^\"]+)\"\s*\)",
            text,
        ):
            class_match = re.search(r"\b(?:class|record)\s+(\w+)", text[match.end() :])
            property_bindings.append(
                {
                    "class": class_match.group(1) if class_match else None,
                    "prefix": match.group(1),
                    "source": {
                        "file": relative(root, path),
                        "line": source_line(text, match.start()),
                    },
                }
            )
        for match in re.finditer(r"@Value\s*\(\s*\"\$\{([^}]+)\}\"\s*\)", text):
            value_injections.append(
                {
                    "expression": match.group(1),
                    "source": {
                        "file": relative(root, path),
                        "line": source_line(text, match.start()),
                    },
                }
            )
    env_names = {
        reference["name"]
        for value in values
        for reference in value["environmentReferences"]
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
    resource_root = root / "app/src/main/resources"
    patterns = {
        "font": "fonts/**/*",
        "prompt": "prompts/**/*",
        "redis-script": "scripts/**/*",
        "skill": "skills/**/*",
        "voice-config": "voice-interview-opening.yml",
    }
    resources: list[dict[str, Any]] = []
    for category, pattern in patterns.items():
        for path in sorted(resource_root.glob(pattern)):
            if path.is_file():
                resources.append(resource_entry(root, path, category))
    tests: list[dict[str, Any]] = []
    test_roots = [root / "app/src/test", root / "frontend/e2e", root / "frontend/src"]
    for test_root in test_roots:
        if not test_root.exists():
            continue
        for path in sorted(test_root.glob("**/*")):
            if not path.is_file():
                continue
            if not (
                path.suffix in {".java", ".ts", ".tsx"}
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
            "disabledTestMarkerCount": sum(
                item["disabledMarkers"] for item in tests
            ),
            "resourceCount": len(resources),
            "resourceCountsByCategory": dict(sorted(category_counts.items())),
            "testFileCount": len(tests),
        },
        "resources": resources,
        "tests": tests,
    }


def extract_known_issues(root: Path) -> dict[str, Any]:
    plan = root / "docs/MIGRATION_PLAN.md"
    lines = plan.read_text(encoding="utf-8").splitlines()
    start = lines.index("### 3.2 已确认的现有问题")
    issues: list[dict[str, Any]] = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("## "):
            break
        if line.startswith("- "):
            issues.append(
                {
                    "id": f"KNOWN-{len(issues) + 1:03d}",
                    "requiredAction": "Add a fixed sample that preserves the current behavior.",
                    "source": {
                        "file": relative(root, plan),
                        "line": index + 1,
                    },
                    "status": "sample-required",
                    "summary": line[2:].strip(),
                }
            )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "summary": {"knownIssueCount": len(issues)},
        "issues": issues,
    }


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = (args.output or root / "migration/manifests").resolve()
    manifests = {
        "api.json": build_api_manifest(root),
        "configuration.json": extract_configuration(root),
        "database.json": extract_database(root),
        "known-issues.json": extract_known_issues(root),
        "redis.json": extract_redis(root),
        "resources.json": extract_resources(root),
    }
    for name, value in manifests.items():
        write_json(output, name, value)
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "manifests": {
            name: value["summary"] for name, value in sorted(manifests.items())
        },
        "nextRequiredWork": [
            "Record fixed runtime request/response/error samples.",
            "Capture PostgreSQL catalog, Redis runtime state, S3 metadata, SSE bytes, and WebSocket transcripts.",
            "Establish isolated Java/Python comparison environments.",
        ],
    }
    write_json(output, "summary.json", summary)


if __name__ == "__main__":
    main()
