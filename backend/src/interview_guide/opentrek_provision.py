from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from interview_guide.infrastructure.opentrek.provision import (
    OpenTrekProvisionClient,
    OpenTrekProvisioner,
    mapping_json,
    package_skill_archives,
    read_env_file,
    update_env_values,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="幂等配置 InterviewGuide 校园赛所需的 OpenTrek 资源",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env.campus"))
    parser.add_argument("--cookie-file", type=Path, required=True)
    parser.add_argument("--management-base-url", default="http://10.128.203.200:30226")
    parser.add_argument("--workspace-code")
    parser.add_argument(
        "--agent-model",
        help="可选：用同一模型覆盖四类 Agent 的能力级默认选模",
    )
    parser.add_argument("--no-skills", action="store_true")
    parser.add_argument("--knowledge-file", type=Path, action="append", default=[])
    parser.add_argument("--kortex-kb-code", default="")
    parser.add_argument("--kortex-template-kb-code", default="")
    asyncio.run(run(parser.parse_args()))


async def run(arguments: argparse.Namespace) -> None:
    env_file: Path = arguments.env_file
    cookie_file: Path = arguments.cookie_file
    if not env_file.is_file():
        raise SystemExit(f"环境文件不存在: {env_file}")
    if not cookie_file.is_file():
        raise SystemExit(f"管理 Cookie 文件不存在: {cookie_file}")
    cookie = load_management_cookie(cookie_file)
    if not cookie:
        raise SystemExit("管理 Cookie 文件为空")
    environment = read_env_file(env_file)
    workspace_code = (
        arguments.workspace_code or environment.get("APP_OPENTREK_WORKSPACE_CODE", "")
    ).strip()
    if not workspace_code:
        raise SystemExit("请通过 --workspace-code 或 .env.campus 配置 OpenTrek 工作空间")
    source_files = [path.resolve() for path in arguments.knowledge_file]
    for path in source_files:
        if not path.is_file():
            raise SystemExit(f"知识库资料不存在: {path}")
    client = OpenTrekProvisionClient(
        arguments.management_base_url,
        workspace_code,
        cookie,
    )
    provisioner = OpenTrekProvisioner(client, agent_model_name=arguments.agent_model)
    try:
        app_key = await provisioner.ensure_service_app_key(
            environment.get("APP_OPENTREK_APP_KEY", "")
        )
        update_env_values(
            env_file,
            {
                "APP_OPENTREK_APP_KEY": app_key,
                "APP_OPENTREK_WORKSPACE_CODE": workspace_code,
            },
        )
        agents = await provisioner.ensure_agents()
        update_values = {
            "APP_OPENTREK_APP_KEY": app_key,
            "APP_OPENTREK_WORKSPACE_CODE": workspace_code,
        }
        for prefix, agent in agents.items():
            update_values[f"APP_OPENTREK_{prefix}_AGENT_CODE"] = agent.code
            update_values[f"APP_OPENTREK_{prefix}_AGENT_VERSION"] = agent.version
        with tempfile.TemporaryDirectory(prefix="interview-guide-opentrek-") as directory:
            artifact_root = Path(directory)
            archives = (
                []
                if arguments.no_skills
                else package_skill_archives(
                    Path(__file__).resolve().parents[2] / "resources" / "skills",
                    artifact_root / "skills",
                )
            )
            skills = await provisioner.ensure_skills(archives, agents)
            knowledge_base = await provisioner.ensure_knowledge_base(
                source_files,
                existing_code=arguments.kortex_kb_code or mapped_kb_code(environment, source_files),
                template_code=arguments.kortex_template_kb_code,
            )
        if knowledge_base is not None:
            update_values["APP_OPENTREK_KB_MAPPINGS_JSON"] = mapping_json(
                source_files,
                knowledge_base.code,
            )
        update_env_values(env_file, update_values)
        print(
            json.dumps(
                {
                    "workspaceCode": workspace_code,
                    "agents": {
                        prefix.lower(): {"code": agent.code, "version": agent.version}
                        for prefix, agent in agents.items()
                    },
                    "skillCount": len(skills),
                    "knowledgeBaseCode": knowledge_base.code if knowledge_base else None,
                    "envFile": str(env_file),
                    "appKeyStored": True,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    finally:
        await client.close()


def mapped_kb_code(environment: dict[str, str], files: list[Path]) -> str:
    raw = environment.get("APP_OPENTREK_KB_MAPPINGS_JSON", "[]")
    try:
        values = json.loads(raw)
    except ValueError:
        return ""
    if not isinstance(values, list):
        return ""
    hashes = {mapping_hash(path) for path in files}
    codes = {
        str(item.get("kbCode") or "")
        for item in values
        if isinstance(item, dict) and str(item.get("fileHash") or "") in hashes
    }
    return next(iter(codes)) if len(codes) == 1 else ""


def mapping_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_management_cookie(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return ""
    if not raw.startswith("{"):
        return raw
    try:
        state = json.loads(raw)
    except ValueError as error:
        raise SystemExit(
            "管理 Cookie 文件不是合法的 Cookie Header 或 Playwright storageState"
        ) from error
    cookies = state.get("cookies") if isinstance(state, dict) else None
    if not isinstance(cookies, list):
        raise SystemExit("Playwright storageState 缺少 cookies")
    values = [
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if isinstance(cookie, dict)
        and isinstance(cookie.get("name"), str)
        and isinstance(cookie.get("value"), str)
        and str(cookie.get("domain") or "").lstrip(".") == "10.128.203.200"
    ]
    if not values:
        raise SystemExit("Playwright storageState 中没有 OpenTrek 管理站 Cookie")
    return "; ".join(values)
