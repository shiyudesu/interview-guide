from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx
import pytest

from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.infrastructure.opentrek.provision import (
    AGENT_DEFINITIONS,
    AGENT_VERSION_NAME,
    DEFAULT_AGENT_MODELS,
    OpenTrekProvisionClient,
    OpenTrekProvisioner,
    agent_model_config,
    embedding_model_config,
    extract_created_secret,
    package_skill_archives,
    read_env_file,
    update_env_values,
)
from interview_guide.opentrek_provision import load_management_cookie, mapped_kb_code


async def test_provision_client_separates_cookie_and_app_key_auth() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"success": True, "data": {"ok": True}})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenTrekProvisionClient(
        "http://10.128.203.200:30226",
        "workspace-one",
        "SESSION=protected-cookie",
        client=http_client,
    )
    await client.management("POST", "/agent/version/online", payload={"agentCode": "a"})
    client.set_app_key("protected-app-key")
    await client.openapi("POST", "/agent/openapi/agent/pageQuery", payload={"current": 1})
    await http_client.aclose()

    management, openapi = requests
    assert management.url.path == "/agent/version/online"
    assert management.headers["cookie"] == "SESSION=protected-cookie"
    assert "authorization" not in management.headers
    assert openapi.url.path == "/gatectl/agent/openapi/agent/pageQuery"
    assert openapi.headers["authorization"] == "Bearer protected-app-key"
    assert "cookie" not in openapi.headers
    assert all(request.headers["x-sfm-workspacecode"] == "workspace-one" for request in requests)
    assert management.headers["projectcode"] == "workspace-one"
    assert management.headers["x-sfm-workspace"] == "workspace-one"


def test_competition_v12_uses_glm_5_1_for_every_capability() -> None:
    assert AGENT_VERSION_NAME == "competition-v12"
    assert set(DEFAULT_AGENT_MODELS) == set(AGENT_DEFINITIONS)
    assert set(DEFAULT_AGENT_MODELS.values()) == {"glm-5.1"}


async def test_provision_client_rejects_redirected_login() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(302, headers={"Location": "/agent/index.html#/login"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenTrekProvisionClient(
        "http://10.128.203.200:30226",
        "workspace-one",
        "expired-cookie",
        client=http_client,
    )
    with pytest.raises(BusinessException) as caught:
        await client.management("GET", "/agent/status")
    await http_client.aclose()

    assert caught.value.code == ErrorCode.UNAUTHORIZED.code
    assert "Cookie" in caught.value.message


class FakeProvisionClient:
    def __init__(self) -> None:
        self.workspace_code = "workspace-one"
        self.app_key = ""
        self.agents: dict[str, dict[str, str]] = {}
        self.versions: dict[str, dict[str, str]] = {}
        self.management_calls: list[tuple[str, dict[str, object]]] = []

    def set_app_key(self, value: str) -> None:
        self.app_key = value

    async def management(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        del method, params
        values = payload or {}
        self.management_calls.append((path, values))
        if path.endswith("createKey"):
            return {"masterSecretKey": "created-app-key"}
        if path.endswith("getSkillFileModePermission"):
            return True
        if path.endswith("setSkillFileModePermission"):
            return True
        if path.endswith("config/query"):
            return {
                "nodeFormAttribute": [
                    {
                        "nodeId": "node_model",
                        "taskPlanning": {"modelConfigMode": "normal", "modelType": "llm"},
                    },
                    {"nodeId": "node_role", "extend": []},
                    {"nodeId": "node_constraint", "extend": []},
                ]
            }
        if path.endswith("listAvailableModels"):
            requested_model = str(values.get("modelName") or "qwen3.6-plus")
            return {
                "list": [
                    {
                        "name": requested_model,
                        "code": "model-code",
                        "version": "OPENTREK_MODEL_DEFAULT_VERSION",
                        "source": "AGENT_THIRD_PARTY",
                        "modelExtParams": [],
                    }
                ]
            }
        if path.endswith("config/update"):
            return True
        if path.endswith("version/offline"):
            code = str(values["agentCode"])
            self.versions[code]["agentStatus"] = "DEV"
            return True
        if path.endswith("version/online"):
            code = str(values["agentCode"])
            self.versions[code]["agentStatus"] = "ONLINE"
            return True
        raise AssertionError(path)

    async def openapi(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        del method, params
        values = payload or {}
        if path.endswith("agent/pageQuery"):
            name = str(values["agentName"])
            record = self.agents.get(name)
            return {"list": [record] if record else []}
        if path.endswith("agent/create"):
            name = str(values["agentName"])
            record = {"agentName": name, "agentCode": f"code-{len(self.agents) + 1}"}
            self.agents[name] = record
            return record
        if path.endswith("agent/version/pageQuery"):
            code = str(values["agentCode"])
            record = self.versions.get(code)
            return {"list": [record] if record else []}
        if path.endswith("agent/version/create"):
            code = str(values["agentCode"])
            record = {
                "agentCode": code,
                "agentVersion": f"version-{len(self.versions) + 1}",
                "versionName": AGENT_VERSION_NAME,
                "agentStatus": "DEV",
            }
            self.versions[code] = record
            return record
        raise AssertionError(path)


class FakeKortexProvisionClient:
    def __init__(self) -> None:
        self.workspace_code = "workspace-one"
        self.openapi_calls: list[tuple[str, dict[str, object]]] = []
        self.uploads: list[tuple[str, bytes, str]] = []

    async def management(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        del method
        if path.endswith("listAvailableModels"):
            model_type = str((payload or {})["modelType"])
            name = "text-embedding-v4" if model_type == "EMBEDDING" else "qwen-vl-plus"
            return {
                "list": [
                    {
                        "name": name,
                        "code": f"service-{model_type}",
                        "modelCode": name,
                        "version": "OPENTREK_MODEL_DEFAULT_VERSION",
                        "source": "AGENT_THIRD_PARTY",
                        "modelExtParams": (
                            [{"code": "dimensions", "value": None}]
                            if model_type == "EMBEDDING"
                            else []
                        ),
                    }
                ]
            }
        if path.endswith("getMediaOSSPolicyByName"):
            assert params == {"fileName": "fixture.md"}
            return {
                "preSignedUrl": "http://10.128.203.183:30017/upload?signature=redacted",
                "downloadUrl": "http://10.128.203.183:30017/download/fixture.md",
            }
        raise AssertionError(path)

    async def openapi(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        del method, params
        values = payload or {}
        self.openapi_calls.append((path, values))
        if path.endswith("kb/list"):
            return {"list": []}
        if path.endswith("kb/create"):
            return {"kbCode": "kb-created"}
        if path.endswith("file/data/sync"):
            outer_code = str(values["fileInfo"][0]["fileOuterCode"])  # type: ignore[index]
            return {"insert": 1, "insertMap": {outer_code: "file-created"}}
        if path.endswith("doc/file/list"):
            return {
                "list": [
                    {
                        "fileCode": "file-created",
                        "fileOriginalName": "fixture.md",
                        "state": 200,
                    }
                ]
            }
        raise AssertionError(path)

    async def upload_presigned(
        self,
        url: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self.uploads.append((url, content, content_type))


async def test_provisioner_rejects_unstable_deepseek_agent_model() -> None:
    provisioner = OpenTrekProvisioner(FakeProvisionClient())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="无规划任务结果"):
        await provisioner._selected_agent_model("deepseek-v4-pro")


async def test_provisioner_creates_key_agents_versions_and_publishes() -> None:
    fake = FakeProvisionClient()
    provisioner = OpenTrekProvisioner(fake)  # type: ignore[arg-type]

    key = await provisioner.ensure_service_app_key("")
    agents = await provisioner.ensure_agents()

    assert key == "created-app-key"
    assert fake.app_key == key
    assert set(agents) == set(AGENT_DEFINITIONS)
    assert len(fake.agents) == 4
    assert all(value["agentStatus"] == "ONLINE" for value in fake.versions.values())
    publish_calls = [call for call in fake.management_calls if call[0].endswith("online")]
    config_calls = [call for call in fake.management_calls if call[0].endswith("config/update")]
    assert len(publish_calls) == 4
    assert len(config_calls) == 4
    configured_nodes = config_calls[0][1]["nodeFormAttribute"]
    assert isinstance(configured_nodes, list)
    role = next(node for node in configured_nodes if node["nodeId"] == "node_role")
    constraint = next(node for node in configured_nodes if node["nodeId"] == "node_constraint")
    assert role["extend"][0]["nodeAttributeValue"]
    assert constraint["extend"][0]["nodeAttributeValue"]


async def test_provisioner_creates_and_waits_for_document_knowledge_base(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.md"
    source.write_text("校园赛知识库", encoding="utf-8")
    fake = FakeKortexProvisionClient()
    provisioner = OpenTrekProvisioner(fake)  # type: ignore[arg-type]

    result = await provisioner.ensure_knowledge_base(
        [source],
        existing_code="",
        template_code="",
    )

    assert result is not None
    assert result.code == "kb-created"
    assert fake.uploads[0][2] == "text/markdown"
    create_payload = next(
        payload for path, payload in fake.openapi_calls if path.endswith("kb/create")
    )
    properties = create_payload["kbProperties"]
    assert isinstance(properties, dict)
    assert properties["textModel"]["modelCode"] == "service-EMBEDDING"
    assert properties["textModel"]["modelExtParams"][0]["value"] == "1024"
    assert properties["visualModel"]["modelCode"] == "service-vlm"
    assert properties["processStrategy"]["processStrategyMethod"] == "simple"


def test_package_skill_archives_include_only_referenced_material(tmp_path: Path) -> None:
    skills_root = Path(__file__).resolve().parents[2] / "resources" / "skills"

    archives = package_skill_archives(skills_root, tmp_path)

    assert len(archives) == 13
    by_name = {path.stem: path for path in archives}
    with zipfile.ZipFile(by_name["java-backend"]) as package:
        names = set(package.namelist())
        assert "SKILL.md" in names
        assert "skill.meta.yml" in names
        assert "_shared/references/java.md" in names
        assert "_shared/references/kubernetes.md" not in names
    with zipfile.ZipFile(by_name["ai-agent-dev"]) as package:
        assert "ai-agent-dev.md" in package.namelist()
        assert "_shared/references/ai-agent-dev.md" not in package.namelist()


def test_env_update_is_atomic_and_quotes_json_and_secret(tmp_path: Path) -> None:
    path = tmp_path / ".env.campus"
    path.write_text(
        "APP_OPENTREK_APP_KEY=\nAPP_OPENTREK_KB_MAPPINGS_JSON='[]'\nUNCHANGED=yes\n",
        encoding="utf-8",
    )
    mappings = json.dumps([{"fileHash": "a" * 64, "kbCode": "kb one"}])

    update_env_values(
        path,
        {
            "APP_OPENTREK_APP_KEY": "secret with spaces",
            "APP_OPENTREK_KB_MAPPINGS_JSON": mappings,
        },
    )

    parsed = read_env_file(path)
    assert parsed["APP_OPENTREK_APP_KEY"] == "secret with spaces"
    assert json.loads(parsed["APP_OPENTREK_KB_MAPPINGS_JSON"]) == json.loads(mappings)
    assert parsed["UNCHANGED"] == "yes"
    assert path.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("direct-key", "direct-key"),
        ({"apiKey": "api-key"}, "api-key"),
        ({"masterSecretKey": "master-key"}, "master-key"),
    ],
)
def test_extract_created_secret(document: object, expected: str) -> None:
    assert extract_created_secret(document) == expected


def test_agent_model_config_normalizes_available_model() -> None:
    config = agent_model_config(
        {
            "name": "qwen3.6-flash",
            "code": "model-code",
            "version": "OPENTREK_MODEL_DEFAULT_VERSION",
            "source": "AGENT_THIRD_PARTY",
            "modelExtParams": [
                {"code": "enable_thinking"},
                {"code": "max_tokens"},
                {"code": "temperature"},
            ],
        }
    )

    assert config["modelName"] == "qwen3.6-flash"
    assert config["modelCode"] == "model-code"
    assert config["modelVersion"] == "OPENTREK_MODEL_DEFAULT_VERSION"
    assert config["modelSource"] == "AGENT_THIRD_PARTY"
    assert config["chooseRag"] is False
    assert [item["value"] for item in config["modelExtParams"]] == [False, 4096, 0.1]


def test_embedding_model_config_uses_service_code_and_1024_dimensions() -> None:
    config = embedding_model_config(
        {
            "name": "text-embedding-v4",
            "code": "service-uuid",
            "modelCode": "text-embedding-v4",
            "version": "OPENTREK_MODEL_DEFAULT_VERSION",
            "source": "AGENT_THIRD_PARTY",
            "modelExtParams": [{"code": "dimensions", "value": None}],
        }
    )

    assert config["modelCode"] == "service-uuid"
    assert config["modelType"] == "EMBEDDING"
    assert config["modelExtParams"] == [{"code": "dimensions", "value": "1024"}]


def test_load_management_cookie_accepts_playwright_storage_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "SESSION", "value": "abc", "domain": "10.128.203.200"},
                    {"name": "other", "value": "ignored", "domain": "example.com"},
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )

    assert load_management_cookie(path) == "SESSION=abc"


def test_mapped_kb_code_reuses_only_unambiguous_mapping(tmp_path: Path) -> None:
    source = tmp_path / "fixture.md"
    source.write_text("fixture", encoding="utf-8")
    file_hash = mapping_hash_for_test(source)

    assert (
        mapped_kb_code(
            {
                "APP_OPENTREK_KB_MAPPINGS_JSON": json.dumps(
                    [{"fileHash": file_hash, "kbCode": "kb"}]
                )
            },
            [source],
        )
        == "kb"
    )
    assert mapped_kb_code({"APP_OPENTREK_KB_MAPPINGS_JSON": "not-json"}, [source]) == ""


def mapping_hash_for_test(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
