#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import io
import json
import re
import tarfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_PER_QUERY = 5
DEFAULT_MAX_PER_CATEGORY = 100
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_MARKDOWN_BYTES = 1024 * 1024
MAX_MARKDOWN_TOTAL_BYTES = 50 * 1024 * 1024
COLLECTABLE_KINDS = {"github-json", "github-markdown", "mianshiya-search"}
ALLOWED_KINDS = {*COLLECTABLE_KINDS, "documentation"}
ALLOWED_USAGE = {
    "adapt-with-attribution",
    "discovery-only",
    "link-only",
    "verify-only",
}
MARKDOWN_LINK = re.compile(r"!?(?:\[([^]]*)\])\([^)]+\)")
HTML_TAG = re.compile(r"<[^>]+>")
HEADING = re.compile(r"^#{2,6}\s+(.+?)\s*#*$")
LIST_ITEM = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$")
SUMMARY = re.compile(r"<summary[^>]*>(.*?)</summary>", re.IGNORECASE)
EMPHASIZED_QUESTION = re.compile(r"^\*+\s*Q\??:\s*(.*?)\*+$", re.IGNORECASE)
ANSWER_PREFIX = re.compile(r"^\*?\s*A\s*:\s*", re.IGNORECASE)
TRAILING_ANCHOR = re.compile(r"\s*\{#[^}]+}\s*$")
QUESTION_PREFIXES = (
    "can ",
    "compare ",
    "describe ",
    "do ",
    "does ",
    "explain ",
    "how ",
    "is ",
    "should ",
    "what ",
    "when ",
    "where ",
    "which ",
    "why ",
    "什么",
    "为什么",
    "如何",
    "怎么",
    "请",
    "解释",
    "比较",
    "描述",
    "设计",
    "实现",
    "排查",
    "区别",
    "谈谈",
    "说说",
)
TOPIC_MARKERS = (
    "best practice",
    "common problem",
    "deep dive",
    "internals",
    "overview",
    "详解",
    "原理",
    "机制",
    "最佳实践",
    "常见问题",
)


class ReferenceSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class CategoryConfig:
    key: str
    queries: tuple[str, ...]
    keywords: tuple[str, ...]


JsonFetcher = Callable[[str, Mapping[str, object], float], Mapping[str, object]]
BytesFetcher = Callable[[str, float], bytes]


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReferenceSourceError(f"无法读取配置 {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReferenceSourceError(f"配置根节点必须是对象: {path}")
    return value


def load_catalog(root: Path) -> list[dict[str, Any]]:
    document = load_json(root / "tools/reference_sources/catalog.json")
    values = document.get("sources")
    if not isinstance(values, list):
        raise ReferenceSourceError("catalog.json 缺少 sources 数组")
    return [dict(value) for value in values if isinstance(value, dict)]


def load_taxonomy(root: Path) -> dict[str, tuple[CategoryConfig, ...]]:
    document = load_json(root / "tools/reference_sources/taxonomy.json")
    skills = document.get("skills")
    if not isinstance(skills, dict):
        raise ReferenceSourceError("taxonomy.json 缺少 skills 对象")
    result: dict[str, tuple[CategoryConfig, ...]] = {}
    for skill_id, raw_skill in skills.items():
        if not isinstance(skill_id, str) or not isinstance(raw_skill, dict):
            continue
        raw_categories = raw_skill.get("categories")
        if not isinstance(raw_categories, list):
            continue
        categories: list[CategoryConfig] = []
        for raw_category in raw_categories:
            if not isinstance(raw_category, dict):
                continue
            key = raw_category.get("key")
            queries = raw_category.get("queries")
            keywords = raw_category.get("keywords")
            if not isinstance(key, str):
                continue
            categories.append(
                CategoryConfig(
                    key=key,
                    queries=tuple(item for item in queries or () if isinstance(item, str)),
                    keywords=tuple(item for item in keywords or () if isinstance(item, str)),
                )
            )
        result[skill_id] = tuple(categories)
    return result


def skill_category_keys(root: Path, skill_id: str) -> set[str]:
    metadata = root / "backend/resources/skills" / skill_id / "skill.meta.yml"
    if not metadata.is_file():
        return set()
    return set(
        re.findall(
            r"^\s*-\s+key:\s*([A-Z][A-Z0-9_]*)\s*$",
            metadata.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )


def validate_configuration(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        catalog_document = load_json(root / "tools/reference_sources/catalog.json")
        taxonomy_document = load_json(root / "tools/reference_sources/taxonomy.json")
        provenance_document = load_json(root / "tools/reference_sources/provenance.json")
        sources = load_catalog(root)
        taxonomy = load_taxonomy(root)
    except ReferenceSourceError as error:
        return [str(error)]
    for name, document in (
        ("catalog.json", catalog_document),
        ("taxonomy.json", taxonomy_document),
        ("provenance.json", provenance_document),
    ):
        if document.get("schemaVersion") != SCHEMA_VERSION:
            errors.append(f"{name}: schemaVersion 必须为 {SCHEMA_VERSION}")

    seen_source_ids: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"catalog.json sources[{index}]"
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            errors.append(f"{prefix}: id 不能为空")
            continue
        if source_id in seen_source_ids:
            errors.append(f"{prefix}: source id 重复: {source_id}")
        seen_source_ids.add(source_id)
        kind = source.get("kind")
        usage = source.get("usage")
        if kind not in ALLOWED_KINDS:
            errors.append(f"{prefix}: 不支持的 kind: {kind}")
        if usage not in ALLOWED_USAGE:
            errors.append(f"{prefix}: 不支持的 usage: {usage}")
        for field in ("displayName", "homepage", "license", "licenseUrl"):
            if not isinstance(source.get(field), str) or not source[field]:
                errors.append(f"{prefix}: {field} 不能为空")
        skills = source.get("skills")
        if not isinstance(skills, list) or any(not isinstance(item, str) for item in skills):
            errors.append(f"{prefix}: skills 必须是字符串数组")
        elif any(skill_id not in taxonomy for skill_id in skills):
            invalid = sorted(skill_id for skill_id in skills if skill_id not in taxonomy)
            errors.append(f"{prefix}: 未定义 taxonomy 的 Skill: {', '.join(invalid)}")
        if kind == "mianshiya-search":
            for field in ("endpoint", "resultUrlTemplate"):
                if not isinstance(source.get(field), str) or not source[field]:
                    errors.append(f"{prefix}: {field} 不能为空")
        if kind in {"github-json", "github-markdown"}:
            for field in ("repository", "revision"):
                if not isinstance(source.get(field), str) or not source[field]:
                    errors.append(f"{prefix}: {field} 不能为空")
            revision = source.get("revision")
            if isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision) is None:
                errors.append(f"{prefix}: revision 必须固定为 40 位 commit SHA")
            tracked_branch = source.get("trackedBranch")
            if not isinstance(tracked_branch, str) or not tracked_branch:
                errors.append(f"{prefix}: trackedBranch 不能为空")
            prefixes = source.get("includePrefixes")
            if not isinstance(prefixes, list) or any(
                not isinstance(item, str) for item in prefixes
            ):
                errors.append(f"{prefix}: includePrefixes 必须是字符串数组")
            files = source.get("files", [])
            if not isinstance(files, list) or any(not isinstance(item, str) for item in files):
                errors.append(f"{prefix}: files 必须是字符串数组")
            if kind == "github-json" and not files:
                errors.append(f"{prefix}: github-json 必须配置 files")
        if kind == "github-json":
            for field in ("questionField", "difficultyField", "externalIdField"):
                if not isinstance(source.get(field), str) or not source[field]:
                    errors.append(f"{prefix}: {field} 不能为空")
            tag_fields = source.get("tagFields")
            if not isinstance(tag_fields, list) or any(
                not isinstance(item, str) for item in tag_fields
            ):
                errors.append(f"{prefix}: tagFields 必须是字符串数组")
        if kind == "documentation" and usage != "verify-only":
            errors.append(f"{prefix}: documentation 来源只能使用 verify-only")

    for skill_id, categories in taxonomy.items():
        configured_keys = skill_category_keys(root, skill_id)
        if not configured_keys:
            errors.append(f"taxonomy.json: Skill 不存在或没有分类: {skill_id}")
            continue
        seen_keys: set[str] = set()
        for category in categories:
            prefix = f"taxonomy.json {skill_id}/{category.key}"
            if category.key in seen_keys:
                errors.append(f"{prefix}: 分类重复")
            seen_keys.add(category.key)
            if category.key not in configured_keys:
                errors.append(f"{prefix}: 未在 skill.meta.yml 中定义")
            if not category.queries:
                errors.append(f"{prefix}: queries 不能为空")
            if not category.keywords:
                errors.append(f"{prefix}: keywords 不能为空")

    provenance = provenance_document.get("references")
    if not isinstance(provenance, list):
        errors.append("provenance.json: references 必须是数组")
        return errors
    source_by_id = {str(source.get("id")): source for source in sources}
    seen_reference_files: set[str] = set()
    for index, reference in enumerate(provenance):
        prefix = f"provenance.json references[{index}]"
        if not isinstance(reference, dict):
            errors.append(f"{prefix}: 必须是对象")
            continue
        reference_file = reference.get("file")
        if not isinstance(reference_file, str) or not reference_file:
            errors.append(f"{prefix}: file 不能为空")
            continue
        if reference_file in seen_reference_files:
            errors.append(f"{prefix}: reference file 重复: {reference_file}")
        seen_reference_files.add(reference_file)
        path = root / "backend/resources/skills" / reference_file
        if not path.is_file():
            errors.append(f"{prefix}: reference file 不存在: {reference_file}")
        for field in ("discoverySources", "verificationSources"):
            source_ids = reference.get(field)
            if not isinstance(source_ids, list) or any(
                not isinstance(source_id, str) for source_id in source_ids
            ):
                errors.append(f"{prefix}: {field} 必须是字符串数组")
                continue
            unknown = sorted(set(source_ids).difference(source_by_id))
            if unknown:
                errors.append(f"{prefix}: {field} 含未知来源: {', '.join(unknown)}")
        discovery_ids = reference.get("discoverySources")
        if isinstance(discovery_ids, list):
            verify_only = sorted(
                source_id
                for source_id in discovery_ids
                if source_by_id.get(source_id, {}).get("usage") == "verify-only"
            )
            if verify_only:
                errors.append(
                    f"{prefix}: verify-only 来源不能用于题目发现: {', '.join(verify_only)}"
                )
    return errors


def clean_markdown_text(value: str) -> str:
    value = html.unescape(value)
    value = MARKDOWN_LINK.sub(lambda match: match.group(1) or "", value)
    value = HTML_TAG.sub(" ", value)
    value = TRAILING_ANCHOR.sub("", value)
    value = re.sub(r"[`*_~]", "", value)
    value = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*\d*[:.)-]?|问题\s*\d*[:：]?)\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip(" -|：:")
    return value


def is_question_candidate(value: str, *, heading: bool) -> bool:
    if not 6 <= len(value) <= 200:
        return False
    lowered = value.casefold()
    if value.endswith(("?", "？")):
        return True
    if lowered.startswith(QUESTION_PREFIXES):
        return True
    return heading and any(marker in lowered for marker in TOPIC_MARKERS)


def extract_markdown_candidates(markdown: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    in_answer = False
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(("```", "<!--", "![")):
            continue
        if ANSWER_PREFIX.match(stripped):
            in_answer = True
            continue
        heading_match = HEADING.match(stripped)
        list_match = LIST_ITEM.match(stripped)
        summary_match = SUMMARY.search(stripped)
        emphasized_question_match = EMPHASIZED_QUESTION.match(stripped)
        candidate: str | None = None
        is_heading = False
        if emphasized_question_match is not None:
            candidate = emphasized_question_match.group(1)
            in_answer = False
        elif summary_match is not None:
            candidate = summary_match.group(1)
            in_answer = False
        elif heading_match is not None:
            candidate = heading_match.group(1)
            is_heading = True
            in_answer = False
        elif list_match is not None and not in_answer:
            candidate = list_match.group(1)
        if candidate is None:
            continue
        cleaned = clean_markdown_text(candidate)
        normalized = normalize_title(cleaned)
        if normalized in seen or not is_question_candidate(cleaned, heading=is_heading):
            continue
        seen.add(normalized)
        values.append(cleaned)
    return values


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def match_category(
    title: str,
    categories: Sequence[CategoryConfig],
) -> CategoryConfig | None:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    scored = [
        (
            sum(1 for keyword in category.keywords if keyword_matches(normalized, keyword)),
            -index,
            category,
        )
        for index, category in enumerate(categories)
    ]
    score, _, category = max(scored, default=(0, 0, None), key=lambda item: item[:2])
    return category if score > 0 else None


def keyword_matches(normalized_title: str, keyword: str) -> bool:
    normalized_keyword = unicodedata.normalize("NFKC", keyword).casefold()
    if not normalized_keyword:
        return False
    if normalized_keyword.isascii():
        return (
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])",
                normalized_title,
            )
            is not None
        )
    return normalized_keyword in normalized_title


def fetch_json(
    url: str,
    payload: Mapping[str, object],
    timeout: float,
) -> Mapping[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "interview-guide-reference-collector/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError) as error:
        raise ReferenceSourceError(f"请求失败 {url}: {error}") from error
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceSourceError(f"来源返回了无效 JSON: {url}") from error
    if not isinstance(result, dict):
        raise ReferenceSourceError(f"来源返回的 JSON 根节点不是对象: {url}")
    return result


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "interview-guide-reference-collector/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = response.read(MAX_ARCHIVE_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise ReferenceSourceError(f"下载失败 {url}: {error}") from error
    if len(value) > MAX_ARCHIVE_BYTES:
        raise ReferenceSourceError(f"来源归档超过 {MAX_ARCHIVE_BYTES} 字节限制: {url}")
    return value


def collect_mianshiya(
    source: Mapping[str, Any],
    skill_id: str,
    categories: Sequence[CategoryConfig],
    *,
    max_per_query: int = DEFAULT_MAX_PER_QUERY,
    query_limit: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    json_fetcher: JsonFetcher = fetch_json,
) -> list[dict[str, Any]]:
    endpoint = str(source["endpoint"])
    result_url_template = str(source["resultUrlTemplate"])
    candidates: list[dict[str, Any]] = []
    query_count = 0
    for category in categories:
        for query in category.queries:
            if query_limit is not None and query_count >= query_limit:
                return candidates
            query_count += 1
            response = json_fetcher(endpoint, {"searchText": query}, timeout)
            if response.get("code") != 0:
                raise ReferenceSourceError(
                    f"{source['id']} 查询失败 query={query!r} code={response.get('code')!r}"
                )
            data = response.get("data")
            records = data.get("records") if isinstance(data, dict) else None
            if not isinstance(records, list):
                raise ReferenceSourceError(f"{source['id']} 查询结果缺少 records query={query!r}")
            for record in records[:max_per_query]:
                if not isinstance(record, dict):
                    continue
                title = clean_markdown_text(str(record.get("title") or ""))
                external_id = str(record.get("id") or "")
                if not title or not external_id:
                    continue
                raw_tags = record.get("tagList")
                tags = sorted({str(tag).strip() for tag in raw_tags or () if str(tag).strip()})
                candidates.append(
                    {
                        "categoryKey": category.key,
                        "difficulty": difficulty_name(record.get("difficulty")),
                        "queries": [query],
                        "skillId": skill_id,
                        "sources": [
                            source_reference(
                                source,
                                result_url_template.format(id=external_id),
                                external_id=external_id,
                            )
                        ],
                        "tags": tags,
                        "title": title,
                    }
                )
    return candidates


def difficulty_name(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return {1: "junior", 3: "mid", 5: "senior"}.get(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        return {
            "advanced": "senior",
            "beginner": "junior",
            "easy": "junior",
            "hard": "senior",
            "intermediate": "mid",
            "medium": "mid",
            "mid": "mid",
            "senior": "senior",
        }.get(normalized)
    return None


def source_reference(
    source: Mapping[str, Any],
    url: str,
    *,
    external_id: str | None = None,
) -> dict[str, str]:
    result = {
        "license": str(source["license"]),
        "sourceId": str(source["id"]),
        "url": url,
        "usage": str(source["usage"]),
    }
    if external_id is not None:
        result["externalId"] = external_id
    revision = source.get("revision")
    if isinstance(revision, str) and revision:
        result["revision"] = revision
    return result


def github_archive_url(source: Mapping[str, Any]) -> str:
    return f"https://codeload.github.com/{source['repository']}/tar.gz/{source['revision']}"


def github_raw_url(source: Mapping[str, Any], path: str) -> str:
    quoted_path = urllib.parse.quote(path)
    return (
        f"https://raw.githubusercontent.com/{source['repository']}/"
        f"{source['revision']}/{quoted_path}"
    )


def included_path(path: str, prefixes: Sequence[str]) -> bool:
    if not prefixes:
        return True
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def markdown_documents_from_archive(
    archive_bytes: bytes,
    include_prefixes: Sequence[str],
) -> Iterable[tuple[str, str]]:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            members = sorted(archive.getmembers(), key=lambda item: item.name)
            total_markdown_bytes = 0
            for member in members:
                if not member.isfile() or member.size > MAX_MARKDOWN_BYTES:
                    continue
                _, separator, relative_path = member.name.partition("/")
                if not separator or not relative_path.endswith(".md"):
                    continue
                if not included_path(relative_path, include_prefixes):
                    continue
                total_markdown_bytes += member.size
                if total_markdown_bytes > MAX_MARKDOWN_TOTAL_BYTES:
                    raise ReferenceSourceError("GitHub 归档内 Markdown 超过允许的解压读取上限")
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                yield relative_path, extracted.read().decode("utf-8", errors="replace")
    except (tarfile.TarError, OSError) as error:
        raise ReferenceSourceError(f"无法读取 GitHub 归档: {error}") from error


def github_markdown_documents(
    source: Mapping[str, Any],
    *,
    timeout: float,
    bytes_fetcher: BytesFetcher,
) -> Iterable[tuple[str, str]]:
    files = tuple(str(path) for path in source.get("files", ()) if isinstance(path, str))
    if files:
        for path in sorted(files):
            content = bytes_fetcher(github_raw_url(source, path), timeout)
            if len(content) > MAX_MARKDOWN_BYTES:
                raise ReferenceSourceError(
                    f"GitHub Markdown 超过 {MAX_MARKDOWN_BYTES} 字节限制: {path}"
                )
            yield path, content.decode("utf-8", errors="replace")
        return
    archive = bytes_fetcher(github_archive_url(source), timeout)
    prefixes = tuple(
        str(prefix) for prefix in source.get("includePrefixes", ()) if isinstance(prefix, str)
    )
    yield from markdown_documents_from_archive(archive, prefixes)


def collect_github_markdown(
    source: Mapping[str, Any],
    taxonomy: Mapping[str, Sequence[CategoryConfig]],
    requested_skills: set[str],
    *,
    max_per_category: int = DEFAULT_MAX_PER_CATEGORY,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    bytes_fetcher: BytesFetcher = fetch_bytes,
) -> list[dict[str, Any]]:
    source_skills = {
        str(skill_id) for skill_id in source.get("skills", ()) if isinstance(skill_id, str)
    }
    skills = sorted(source_skills.intersection(requested_skills))
    if not skills:
        return []
    counts: dict[tuple[str, str], int] = {}
    candidates: list[dict[str, Any]] = []
    repository = str(source["repository"])
    revision = str(source["revision"])
    for path, markdown in github_markdown_documents(
        source,
        timeout=timeout,
        bytes_fetcher=bytes_fetcher,
    ):
        source_url = f"https://github.com/{repository}/blob/{revision}/{urllib.parse.quote(path)}"
        for title in extract_markdown_candidates(markdown):
            for skill_id in skills:
                category = match_category(title, taxonomy[skill_id])
                if category is None:
                    continue
                count_key = (skill_id, category.key)
                if counts.get(count_key, 0) >= max_per_category:
                    continue
                counts[count_key] = counts.get(count_key, 0) + 1
                candidates.append(
                    {
                        "categoryKey": category.key,
                        "difficulty": None,
                        "queries": [],
                        "skillId": skill_id,
                        "sources": [source_reference(source, source_url)],
                        "tags": [],
                        "title": title,
                    }
                )
    return candidates


def collect_github_json(
    source: Mapping[str, Any],
    taxonomy: Mapping[str, Sequence[CategoryConfig]],
    requested_skills: set[str],
    *,
    max_per_category: int = DEFAULT_MAX_PER_CATEGORY,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    bytes_fetcher: BytesFetcher = fetch_bytes,
) -> list[dict[str, Any]]:
    source_skills = {
        str(skill_id) for skill_id in source.get("skills", ()) if isinstance(skill_id, str)
    }
    skills = sorted(source_skills.intersection(requested_skills))
    if not skills:
        return []
    question_field = str(source["questionField"])
    difficulty_field = str(source["difficultyField"])
    external_id_field = str(source["externalIdField"])
    tag_fields = tuple(str(field) for field in source.get("tagFields", ()))
    repository = str(source["repository"])
    revision = str(source["revision"])
    counts: dict[tuple[str, str], int] = {}
    candidates: list[dict[str, Any]] = []
    files = sorted(str(path) for path in source.get("files", ()))
    for path in files:
        content = bytes_fetcher(github_raw_url(source, path), timeout)
        if len(content) > MAX_MARKDOWN_BYTES:
            raise ReferenceSourceError(f"GitHub JSON 超过 {MAX_MARKDOWN_BYTES} 字节限制: {path}")
        try:
            document = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReferenceSourceError(f"GitHub JSON 无法解析: {path}") from error
        if not isinstance(document, list):
            raise ReferenceSourceError(f"GitHub JSON 根节点必须是数组: {path}")
        source_url = f"https://github.com/{repository}/blob/{revision}/{urllib.parse.quote(path)}"
        for record in document:
            if not isinstance(record, dict):
                continue
            title = clean_markdown_text(str(record.get(question_field) or ""))
            if not title:
                continue
            tags = sorted(
                {
                    str(record[field]).strip()
                    for field in tag_fields
                    if record.get(field) is not None and str(record[field]).strip()
                }
            )
            classification_text = " ".join((title, *tags))
            for skill_id in skills:
                category = match_category(classification_text, taxonomy[skill_id])
                if category is None:
                    continue
                count_key = (skill_id, category.key)
                if counts.get(count_key, 0) >= max_per_category:
                    continue
                counts[count_key] = counts.get(count_key, 0) + 1
                external_id = record.get(external_id_field)
                candidates.append(
                    {
                        "categoryKey": category.key,
                        "difficulty": difficulty_name(record.get(difficulty_field)),
                        "queries": [],
                        "skillId": skill_id,
                        "sources": [
                            source_reference(
                                source,
                                source_url,
                                external_id=(str(external_id) if external_id is not None else None),
                            )
                        ],
                        "tags": tags,
                        "title": title,
                    }
                )
    return candidates


def deduplicate_candidates(
    candidates: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            str(candidate["skillId"]),
            str(candidate["categoryKey"]),
            normalize_title(str(candidate["title"])),
        )
        if not key[2]:
            continue
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {
                **candidate,
                "queries": sorted(set(candidate.get("queries", ()))),
                "sources": list(candidate.get("sources", ())),
                "tags": sorted(set(candidate.get("tags", ()))),
            }
            continue
        existing["queries"] = sorted({*existing.get("queries", ()), *candidate.get("queries", ())})
        existing["tags"] = sorted({*existing.get("tags", ()), *candidate.get("tags", ())})
        known_sources = {
            (source.get("sourceId"), source.get("url"))
            for source in existing.get("sources", ())
            if isinstance(source, dict)
        }
        for source in candidate.get("sources", ()):
            if not isinstance(source, dict):
                continue
            source_key = (source.get("sourceId"), source.get("url"))
            if source_key not in known_sources:
                existing["sources"].append(source)
                known_sources.add(source_key)
        if existing.get("difficulty") is None and candidate.get("difficulty") is not None:
            existing["difficulty"] = candidate["difficulty"]
    result = list(grouped.values())
    for candidate in result:
        candidate["sources"] = sorted(
            candidate["sources"],
            key=lambda item: (item.get("sourceId", ""), item.get("url", "")),
        )
    return sorted(
        result,
        key=lambda item: (
            item["skillId"],
            item["categoryKey"],
            unicodedata.normalize("NFKC", item["title"]).casefold(),
        ),
    )


def write_jsonl(path: Path, candidates: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n" for candidate in candidates
    )
    path.write_text(content, encoding="utf-8")


def collect(
    root: Path,
    *,
    source_ids: Sequence[str],
    skill_ids: Sequence[str],
    output: Path,
    max_per_query: int,
    max_per_category: int,
    query_limit: int | None,
    timeout: float,
    all_enabled: bool = False,
) -> list[dict[str, Any]]:
    errors = validate_configuration(root)
    if errors:
        raise ReferenceSourceError("\n".join(errors))
    sources = load_catalog(root)
    taxonomy = load_taxonomy(root)
    known_sources = {str(source["id"]): source for source in sources}
    if source_ids:
        selected_source_ids = list(source_ids)
    elif all_enabled:
        selected_source_ids = [
            source_id
            for source_id, source in known_sources.items()
            if source.get("enabled") is True and source.get("kind") in COLLECTABLE_KINDS
        ]
    else:
        raise ReferenceSourceError("collect 至少需要一个 --source，或显式使用 --all-enabled")
    unknown_sources = sorted(set(selected_source_ids).difference(known_sources))
    if unknown_sources:
        raise ReferenceSourceError(f"未知来源: {', '.join(unknown_sources)}")
    selected_skills = set(skill_ids or taxonomy)
    unknown_skills = sorted(selected_skills.difference(taxonomy))
    if unknown_skills:
        raise ReferenceSourceError(f"未知 Skill: {', '.join(unknown_skills)}")

    candidates: list[dict[str, Any]] = []
    for source_id in selected_source_ids:
        source = known_sources[source_id]
        kind = source.get("kind")
        if kind == "documentation":
            continue
        if kind == "mianshiya-search":
            supported_skills = set(source.get("skills", ())).intersection(selected_skills)
            for skill_id in sorted(supported_skills):
                candidates.extend(
                    collect_mianshiya(
                        source,
                        skill_id,
                        taxonomy[skill_id],
                        max_per_query=max_per_query,
                        query_limit=query_limit,
                        timeout=timeout,
                    )
                )
        elif kind == "github-markdown":
            candidates.extend(
                collect_github_markdown(
                    source,
                    taxonomy,
                    selected_skills,
                    max_per_category=max_per_category,
                    timeout=timeout,
                )
            )
        elif kind == "github-json":
            candidates.extend(
                collect_github_json(
                    source,
                    taxonomy,
                    selected_skills,
                    max_per_category=max_per_category,
                    timeout=timeout,
                )
            )
        else:
            raise ReferenceSourceError(f"来源不可采集: {source_id} ({kind})")
    result = deduplicate_candidates(candidates)
    write_jsonl(output, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="普通面试参考资料来源采集工具")
    parser.add_argument("--root", type=Path, default=repository_root())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="校验来源目录和分类词表")
    subparsers.add_parser("list", help="列出已配置来源")
    collect_parser = subparsers.add_parser("collect", help="采集规范化候选题 JSONL")
    source_group = collect_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", action="append", default=[])
    source_group.add_argument("--all-enabled", action="store_true")
    collect_parser.add_argument("--skill", action="append", default=[])
    collect_parser.add_argument(
        "--output",
        type=Path,
        default=Path(".artifacts/reference-questions.jsonl"),
    )
    collect_parser.add_argument("--max-per-query", type=int, default=DEFAULT_MAX_PER_QUERY)
    collect_parser.add_argument(
        "--max-per-category",
        type=int,
        default=DEFAULT_MAX_PER_CATEGORY,
    )
    collect_parser.add_argument("--query-limit", type=int)
    collect_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    if args.command == "validate":
        errors = validate_configuration(root)
        if errors:
            raise SystemExit("\n".join(errors))
        print("reference source configuration is valid")
        return
    if args.command == "list":
        for source in load_catalog(root):
            enabled = "enabled" if source.get("enabled") is True else "disabled"
            print(
                f"{source['id']}\t{source['kind']}\t{source['usage']}\t"
                f"{source['license']}\t{enabled}"
            )
        return
    if args.max_per_query < 1 or args.max_per_category < 1:
        raise SystemExit("max-per-query 和 max-per-category 必须大于 0")
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        candidates = collect(
            root,
            source_ids=args.source,
            skill_ids=args.skill,
            output=output,
            max_per_query=args.max_per_query,
            max_per_category=args.max_per_category,
            query_limit=args.query_limit,
            timeout=args.timeout,
            all_enabled=args.all_enabled,
        )
    except ReferenceSourceError as error:
        raise SystemExit(str(error)) from error
    print(f"collected {len(candidates)} candidates into {output}")


if __name__ == "__main__":
    main()
