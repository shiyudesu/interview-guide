#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

QUESTION_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?[?？])\s*$")
HEADING_LINE = re.compile(r"^(#{1,6})(\s+.*)$")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从已审核 Skill reference 生成 OpenTrek 校园赛完整知识库",
    )
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".artifacts/opentrek-campus-full-knowledge.md"),
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象: {path}")
    return value


def display_name(metadata: str, skill_id: str) -> str:
    match = re.search(r"^displayName:\s*(.+?)\s*$", metadata, re.MULTILINE)
    return match.group(1).strip() if match else skill_id


def referenced_files(skill_dir: Path, shared_dir: Path, metadata: str) -> list[Path]:
    result: list[Path] = []
    for reference in re.findall(r"^\s+ref:\s*([^\s#]+)", metadata, re.MULTILINE):
        local = skill_dir / reference
        shared = shared_dir / reference
        source = local if local.is_file() else shared
        if not source.is_file():
            raise FileNotFoundError(f"Skill reference 不存在: {skill_dir.name}/{reference}")
        if source not in result:
            result.append(source)
    return result


def shifted_markdown(content: str, levels: int = 2) -> str:
    lines: list[str] = []
    for line in content.strip().splitlines():
        match = HEADING_LINE.match(line)
        if match:
            size = min(6, len(match.group(1)) + levels)
            line = "#" * size + match.group(2)
        lines.append(line)
    return "\n".join(lines)


def extracted_questions(paths: list[Path]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = QUESTION_LINE.match(line)
            if not match:
                continue
            question = " ".join(match.group(1).split())
            key = question.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(question)
    return result


def source_catalog(root: Path) -> dict[str, dict[str, object]]:
    document = load_json(root / "tools/reference_sources/catalog.json")
    values = document.get("sources")
    if not isinstance(values, list):
        raise ValueError("catalog.json 缺少 sources 数组")
    return {
        str(value["id"]): value
        for value in values
        if isinstance(value, dict) and isinstance(value.get("id"), str)
    }


def provenance_by_file(root: Path) -> dict[str, dict[str, object]]:
    document = load_json(root / "tools/reference_sources/provenance.json")
    values = document.get("references")
    if not isinstance(values, list):
        raise ValueError("provenance.json 缺少 references 数组")
    return {
        str(value["file"]): value
        for value in values
        if isinstance(value, dict) and isinstance(value.get("file"), str)
    }


def render(root: Path) -> tuple[str, int, int, int]:
    skills_root = root / "backend/resources/skills"
    shared_dir = skills_root / "_shared/references"
    provenance = provenance_by_file(root)
    catalog = source_catalog(root)
    skill_documents: dict[str, Path] = {}
    skill_names: dict[str, str] = {}
    skill_references: dict[str, list[Path]] = {}
    reference_skills: dict[Path, list[str]] = defaultdict(list)

    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_document = skill_dir / "SKILL.md"
        metadata_document = skill_dir / "skill.meta.yml"
        if not skill_document.is_file() or not metadata_document.is_file():
            continue
        skill_id = skill_dir.name
        metadata = metadata_document.read_text(encoding="utf-8")
        references = referenced_files(skill_dir, shared_dir, metadata)
        skill_documents[skill_id] = skill_document
        skill_names[skill_id] = display_name(metadata, skill_id)
        skill_references[skill_id] = references
        for reference in references:
            reference_skills[reference].append(skill_id)

    if len(skill_documents) != 13:
        raise ValueError(f"预期 13 个岗位 Skill，实际为 {len(skill_documents)} 个")

    lines = [
        "# InterviewGuide OpenTrek 校园赛完整知识库",
        "",
        "本文件由仓库内已审核的 13 个岗位 Skill、reference 和来源登记自动生成。",
        "面试鸭仅按 `link-only` 规则用于题目方向发现，不复制受限正文或题解；技术结论以仓库中",
        "已整理并登记 provenance 的内容为准。",
        "",
        "## 覆盖统计",
        "",
        f"- 岗位方向：{len(skill_documents)} 个",
        f"- 去重技术资料：{len(reference_skills)} 份",
    ]

    questions_by_skill: dict[str, list[str]] = {}
    total_questions = 0
    for skill_id in skill_documents:
        paths = [skill_documents[skill_id], *skill_references[skill_id]]
        questions = extracted_questions(paths)
        questions_by_skill[skill_id] = questions
        total_questions += len(questions)
    lines.extend(
        [
            f"- 按岗位收录的场景问题：{total_questions} 条（跨岗位复用的问题分别保留）",
            "",
            "## 面试题索引",
            "",
            "以下问题来自已审核 reference，用于 Kortex 检索、题库生成和面试方向覆盖。",
        ]
    )
    for skill_id, questions in questions_by_skill.items():
        lines.extend(["", f"### {skill_names[skill_id]}（`{skill_id}`）", ""])
        lines.extend(f"{index}. {question}" for index, question in enumerate(questions, 1))

    lines.extend(["", "## 岗位面试指南", ""])
    for skill_id, path in skill_documents.items():
        lines.extend(
            [
                f"### {skill_names[skill_id]}（`{skill_id}`）",
                "",
                shifted_markdown(path.read_text(encoding="utf-8")),
                "",
            ]
        )

    used_source_ids: set[str] = set()
    lines.extend(["## 审核技术资料", ""])
    for path in sorted(reference_skills, key=lambda value: value.name):
        relative = path.relative_to(skills_root).as_posix()
        record = provenance.get(relative, {})
        discovery = [str(value) for value in record.get("discoverySources", [])]
        verification = [str(value) for value in record.get("verificationSources", [])]
        used_source_ids.update(discovery)
        used_source_ids.update(verification)
        applicable = "、".join(skill_names[skill_id] for skill_id in reference_skills[path])
        lines.extend(
            [
                f"### {path.stem}（适用：{applicable}）",
                "",
                f"来源发现：{', '.join(discovery) or '仓库原创整理'}；"
                f"事实核验：{', '.join(verification) or '无单独登记'}。",
                "",
                shifted_markdown(path.read_text(encoding="utf-8")),
                "",
            ]
        )

    lines.extend(["## 来源与使用边界", ""])
    for source_id in sorted(used_source_ids):
        source = catalog.get(source_id)
        if source is None:
            raise ValueError(f"provenance 引用了未登记来源: {source_id}")
        lines.append(
            f"- {source.get('displayName')}：{source.get('homepage')}；"
            f"许可/条款 `{source.get('license')}`；用途 `{source.get('usage')}`。"
        )
    lines.append("")
    return "\n".join(lines), len(skill_documents), len(reference_skills), total_questions


def main() -> None:
    arguments = parse_args()
    root = arguments.root.resolve()
    output = arguments.output if arguments.output.is_absolute() else root / arguments.output
    content, skill_count, reference_count, question_count = render(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(
        f"generated {output} skills={skill_count} references={reference_count} "
        f"questions={question_count} bytes={len(content.encode('utf-8'))}"
    )


if __name__ == "__main__":
    main()
