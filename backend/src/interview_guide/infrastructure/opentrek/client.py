from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import httpx

from interview_guide.common.ai.adapter import (
    ChatResult,
    LlmAdapter,
    ProviderConfig,
)
from interview_guide.common.ai.opentrek import OpenTrekCapability, OpenTrekProviderConfig
from interview_guide.common.ai.outbound import ProviderOutboundPolicy
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode

logger = logging.getLogger(__name__)
OPENTREK_HOST = "10.128.203.200"
OPENTREK_INTERVIEW_SKILLS = (
    "ai-agent-dev",
    "algorithm",
    "ali-backend",
    "bytedance-backend",
    "data-engineering",
    "devops-sre",
    "frontend",
    "go-backend",
    "java-backend-tencent",
    "java-backend",
    "python-backend",
    "system-design",
    "test-development",
)
SCHEMA_BLOCK_PREFIX = "Here is the JSON Schema instance your output must adhere to:\n```"
OUTPUT_FORMAT_START = "Your response should be in JSON format."


class OpenTrekSseDecoder:
    """Incrementally decode SSE frames, including split and coalesced chunks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._data_lines: list[str] = []

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        events: list[str] = []
        while True:
            newline = self._buffer.find("\n")
            if newline < 0:
                break
            line = self._buffer[:newline]
            self._buffer = self._buffer[newline + 1 :]
            if line.endswith("\r"):
                line = line[:-1]
            events.extend(self._line(line))
        return events

    def finish(self) -> list[str]:
        events: list[str] = []
        if self._buffer:
            line = self._buffer[:-1] if self._buffer.endswith("\r") else self._buffer
            self._buffer = ""
            events.extend(self._line(line))
        events.extend(self._dispatch())
        return events

    def _line(self, line: str) -> list[str]:
        if not line:
            return self._dispatch()
        if line.startswith(":"):
            return []
        field, separator, value = line.partition(":")
        if field != "data":
            return []
        if separator and value.startswith(" "):
            value = value[1:]
        events: list[str] = []
        if self._data_lines and self._complete_json("\n".join(self._data_lines)):
            events.extend(self._dispatch())
        self._data_lines.append(value)
        return events

    def _dispatch(self) -> list[str]:
        if not self._data_lines:
            return []
        value = "\n".join(self._data_lines)
        self._data_lines.clear()
        return [value]

    @staticmethod
    def _complete_json(value: str) -> bool:
        if value.strip() == "[DONE]":
            return True
        try:
            json.loads(value)
        except ValueError:
            return False
        return True


class OpenTrekClient:
    def __init__(
        self,
        settings: Settings,
        outbound_policy: ProviderOutboundPolicy,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._outbound_policy = outbound_policy
        self._agent_lock = asyncio.Lock()
        self._agent_lock_file = settings.opentrek_agent_lock_file.strip()
        self._agent_min_interval = settings.opentrek_agent_min_interval_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            transport=outbound_policy.guarded_http_transport(
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=10)
            ),
            timeout=httpx.Timeout(
                connect=settings.opentrek_connect_timeout_seconds,
                read=settings.opentrek_read_timeout_seconds,
                write=settings.opentrek_read_timeout_seconds,
                pool=settings.opentrek_connect_timeout_seconds,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        provider: OpenTrekProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatResult:
        async with self._agent_execution_gate():
            return await self._chat_without_gate(
                provider,
                messages,
                tools=tools,
                tool_choice=tool_choice,
            )

    async def _chat_without_gate(
        self,
        provider: OpenTrekProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatResult:
        session_id = await self._create_session(provider)
        try:
            document = await self.post_json(
                provider,
                "agent/api/run",
                {
                    "sessionId": session_id,
                    "stream": False,
                    "delta": True,
                    "trace": False,
                    "message": {
                        "text": render_opentrek_prompt(
                            messages,
                            tools,
                            tool_choice,
                            compact_schema=provider.structured_compact_schema,
                        ),
                        "metadata": opentrek_message_metadata(provider),
                        "attachments": [],
                    },
                },
            )
            return self._chat_result(document)
        finally:
            await self._best_effort_session_action(provider, "deleteSession", session_id)

    async def stream_chat(
        self,
        provider: OpenTrekProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._agent_execution_gate():
            stream = self._stream_chat_without_gate(
                provider,
                messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            iterator = stream.__aiter__()
            try:
                async for event in iterator:
                    yield event
            finally:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    await close()

    async def _stream_chat_without_gate(
        self,
        provider: OpenTrekProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        session_id = await self._create_session(provider)
        completed = False
        try:
            decoder = OpenTrekSseDecoder()
            async with self._client.stream(
                "POST",
                await self._validated_url(provider.base_url, "agent/api/run"),
                headers=self._headers(provider.api_key),
                json={
                    "sessionId": session_id,
                    "stream": True,
                    "delta": True,
                    "trace": False,
                    "message": {
                        "text": render_opentrek_prompt(
                            messages,
                            tools,
                            tool_choice,
                            compact_schema=provider.structured_compact_schema,
                        ),
                        "metadata": opentrek_message_metadata(provider),
                        "attachments": [],
                    },
                },
            ) as response:
                self._raise_http_error(response)
                async for chunk in response.aiter_text():
                    for raw_event in decoder.feed(chunk):
                        event, ended = self._stream_event(raw_event)
                        if event is not None:
                            yield event
                        if ended:
                            completed = True
                            return
                for raw_event in decoder.finish():
                    event, ended = self._stream_event(raw_event)
                    if event is not None:
                        yield event
                    if ended:
                        completed = True
                        return
                raise BusinessException(
                    ErrorCode.AI_SERVICE_ERROR,
                    "OpenTrek 流式响应意外中断",
                )
        except httpx.TimeoutException as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_TIMEOUT,
                "OpenTrek 响应超时，请稍后重试",
            ) from error
        except httpx.RequestError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "OpenTrek 暂时不可用，请稍后重试",
            ) from error
        finally:
            if not completed:
                await self._best_effort_session_action(provider, "clearSession", session_id)
            await self._best_effort_session_action(provider, "deleteSession", session_id)

    @asynccontextmanager
    async def _agent_execution_gate(self) -> AsyncIterator[None]:
        async with self._agent_lock:
            descriptor = await self._acquire_shared_agent_lock()
            try:
                yield
            finally:
                if descriptor is not None:
                    try:
                        os.utime(self._agent_lock_file, None)
                    finally:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                        os.close(descriptor)

    async def _acquire_shared_agent_lock(self) -> int | None:
        if not self._agent_lock_file:
            return None
        try:
            descriptor = os.open(
                self._agent_lock_file,
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
        except OSError:
            logger.warning("OpenTrek shared agent gate unavailable; using process-local gate")
            return None
        try:
            while True:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
        except BlockingIOError:
            while True:
                try:
                    await asyncio.sleep(0.1)
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    continue
                except BaseException:
                    os.close(descriptor)
                    raise
        except BaseException:
            os.close(descriptor)
            raise
        elapsed = time.time() - os.fstat(descriptor).st_mtime
        remaining = self._agent_min_interval - elapsed
        try:
            if remaining > 0:
                await asyncio.sleep(remaining)
        except BaseException:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            raise
        return descriptor

    async def post_json(
        self,
        provider: OpenTrekProviderConfig,
        path: str,
        payload: dict[str, Any],
        *,
        workspace_code: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(provider.api_key)
        if workspace_code is not None:
            headers["x-sfm-workspacecode"] = workspace_code
        try:
            response = await self._client.post(
                await self._validated_url(provider.base_url, path),
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_TIMEOUT,
                "OpenTrek 响应超时，请稍后重试",
            ) from error
        except httpx.RequestError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "OpenTrek 暂时不可用，请稍后重试",
            ) from error
        self._raise_http_error(response)
        try:
            document = response.json()
        except ValueError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "OpenTrek 返回了无效 JSON",
            ) from error
        if not isinstance(document, dict):
            raise BusinessException(ErrorCode.AI_SERVICE_ERROR, "OpenTrek 返回结构无效")
        if document.get("success") is False:
            detail = self._safe_error_detail(document)
            raise BusinessException(ErrorCode.AI_SERVICE_ERROR, f"OpenTrek 调用失败：{detail}")
        return document

    async def _create_session(self, provider: OpenTrekProviderConfig) -> str:
        payload: dict[str, str] = {"agentCode": provider.model}
        if provider.agent_version:
            payload["agentVersion"] = provider.agent_version
        document = await self.post_json(provider, "agent/api/createSession", payload)
        data = document.get("data")
        session_id = data.get("uniqueCode") if isinstance(data, dict) else None
        if not isinstance(session_id, str) or not session_id.strip():
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "OpenTrek 创建 Session 返回结构无效",
            )
        return session_id

    async def _best_effort_session_action(
        self,
        provider: OpenTrekProviderConfig,
        action: str,
        session_id: str,
    ) -> None:
        try:
            await self.post_json(
                provider,
                f"agent/api/{action}",
                {"sessionId": session_id},
            )
        except BusinessException as error:
            logger.warning(
                "OpenTrek session cleanup failed action=%s errorCode=%s",
                action,
                error.code,
            )
        except httpx.HTTPError:
            logger.warning("OpenTrek session cleanup transport failed action=%s", action)

    async def _validated_url(self, base_url: str, path: str) -> str:
        base = base_url.strip().rstrip("/")
        parsed = urlsplit(base)
        if parsed.hostname != OPENTREK_HOST:
            raise BusinessException(
                ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                "OpenTrek 只允许连接已配置的校内平台地址",
            )
        url = f"{base}/{path.lstrip('/')}"
        await self._outbound_policy.validate_http_url(url)
        return url

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    @staticmethod
    def _raise_http_error(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 401:
            raise BusinessException(
                ErrorCode.AI_API_KEY_INVALID,
                "OpenTrek APP_KEY 无效或已过期",
            )
        if response.status_code == 403:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "OpenTrek 权限或工作空间不匹配",
            )
        if response.status_code == 429:
            raise BusinessException(
                ErrorCode.AI_RATE_LIMIT_EXCEEDED,
                "OpenTrek 调用频率超限，请稍后重试",
            )
        if response.status_code >= 500:
            raise BusinessException(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "OpenTrek 暂时不可用，请稍后重试",
            )
        raise BusinessException(ErrorCode.AI_SERVICE_ERROR, "OpenTrek 调用失败")

    @staticmethod
    def _safe_error_detail(document: dict[str, Any]) -> str:
        for key in ("errorMsg", "errorMessage", "firstErrorMessage"):
            value = document.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
        return "平台返回失败状态"

    @staticmethod
    def _chat_result(document: dict[str, Any]) -> ChatResult:
        data = document.get("data")
        if not isinstance(data, dict):
            raise BusinessException(ErrorCode.AI_SERVICE_ERROR, "OpenTrek 返回结构无效")
        embedded_error = data.get("error")
        if embedded_error:
            if isinstance(embedded_error, dict):
                content = embedded_error.get("content")
                sources = [embedded_error]
                if isinstance(content, dict):
                    sources.insert(0, content)
                detail = "平台 Agent 返回失败状态"
                for source in sources:
                    value = next(
                        (
                            source[key]
                            for key in (
                                "errorMsg",
                                "errorMessage",
                                "message",
                                "detail",
                                "code",
                            )
                            if source.get(key)
                        ),
                        None,
                    )
                    if value is not None:
                        detail = str(value)
                        break
            else:
                detail = str(embedded_error)
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                f"OpenTrek Agent 执行失败：{detail[:300]}",
            )
        message = data.get("message")
        if not isinstance(message, dict):
            raise BusinessException(ErrorCode.AI_SERVICE_ERROR, "OpenTrek 返回消息结构无效")
        content_items = message.get("content")
        text_parts: list[str] = []
        if isinstance(content_items, list):
            for item in content_items:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = item.get("text")
                value = text.get("value") if isinstance(text, dict) else None
                if isinstance(value, str):
                    text_parts.append(value)
        content = final_json_snapshot("".join(text_parts))
        usage = data.get("usage")
        return ChatResult(
            content=content or None,
            message=dict(message),
            usage=usage if isinstance(usage, dict) else None,
            raw=document,
        )

    @staticmethod
    def _stream_event(raw_event: str) -> tuple[dict[str, Any] | None, bool]:
        if raw_event.strip() == "[DONE]":
            return None, True
        try:
            event = json.loads(raw_event)
        except ValueError as error:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                "OpenTrek SSE 包含无效 JSON",
            ) from error
        if not isinstance(event, dict):
            raise BusinessException(ErrorCode.AI_SERVICE_ERROR, "OpenTrek SSE 事件结构无效")
        object_type = event.get("object")
        if object_type == "error":
            content = event.get("content")
            detail = content.get("errorMsg") if isinstance(content, dict) else None
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                f"OpenTrek Agent 执行失败：{str(detail or '未知错误')[:300]}",
            )
        if object_type == "thought.delta":
            return None, False
        if object_type != "message.delta":
            return None, False
        values: list[str] = []
        content = event.get("content")
        items = content if isinstance(content, list) else [content]
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            value = text.get("value") if isinstance(text, dict) else None
            if isinstance(value, str):
                values.append(value)
        value = "".join(values)
        converted = (
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": value},
                        "finish_reason": "stop" if event.get("end") is True else None,
                    }
                ]
            }
            if value or event.get("end") is True
            else None
        )
        return converted, event.get("end") is True


class OpenTrekRoutingLlmAdapter(LlmAdapter):
    def __init__(
        self,
        outbound_policy: ProviderOutboundPolicy,
        settings: Settings,
        opentrek_client: OpenTrekClient | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(outbound_policy, client)
        self._opentrek = opentrek_client or OpenTrekClient(settings, outbound_policy)

    async def close(self) -> None:
        await self._opentrek.close()
        await super().close()

    async def chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        if isinstance(provider, OpenTrekProviderConfig):
            del temperature
            return await self._opentrek.chat(
                provider,
                messages,
                tools=tools,
                tool_choice=tool_choice,
            )
        return await super().chat(
            provider,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )

    async def stream_chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        if isinstance(provider, OpenTrekProviderConfig):
            del temperature
            async for event in self._opentrek.stream_chat(
                provider,
                messages,
                tools=tools,
                tool_choice=tool_choice,
            ):
                yield event
            return
        async for event in super().stream_chat(
            provider,
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        ):
            yield event


def render_opentrek_prompt(
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    *,
    compact_schema: bool = False,
) -> str:
    sections = [
        "你是 InterviewGuide 的受控模型执行节点。请严格遵循下列按角色分隔的消息，"
        "直接输出最终业务结果，不要复述这些边界。",
    ]
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role") or "user").upper()
        content = message.get("content")
        if isinstance(content, str):
            rendered = compact_opentrek_schema(content) if compact_schema else content
        else:
            rendered = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        sections.append(f'<MESSAGE index="{index}" role="{role}">\n{rendered}\n</MESSAGE>')
    if tools:
        sections.append(
            "<TOOLS>\n"
            + json.dumps(list(tools), ensure_ascii=False, separators=(",", ":"))
            + "\n</TOOLS>"
        )
    if tool_choice is not None:
        sections.append(
            "<TOOL_CHOICE>\n"
            + json.dumps(tool_choice, ensure_ascii=False, separators=(",", ":"))
            + "\n</TOOL_CHOICE>"
        )
    return "\n\n".join(sections)


def compact_opentrek_schema(content: str) -> str:
    format_start = content.find(OUTPUT_FORMAT_START)
    schema_marker = content.find(SCHEMA_BLOCK_PREFIX)
    if format_start < 0 or schema_marker < 0:
        return content
    schema_start = schema_marker + len(SCHEMA_BLOCK_PREFIX)
    schema_end = content.find("```", schema_start)
    if schema_end < 0:
        return content
    try:
        schema = json.loads(content[schema_start:schema_end])
    except ValueError:
        return content
    compact = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    replacement = "只返回符合以下 JSON Schema 的 RFC8259 JSON，不要 Markdown 或解释：\n" + compact
    return content[:format_start] + replacement + content[schema_end + 3 :]


def final_json_snapshot(content: str) -> str:
    decoder = json.JSONDecoder()
    index = 0
    snapshots: list[Any] = []
    while index < len(content):
        while index < len(content) and content[index].isspace():
            index += 1
        if index >= len(content):
            break
        try:
            value, end = decoder.raw_decode(content, index)
        except ValueError:
            return content
        snapshots.append(value)
        index = end
    if len(snapshots) <= 1:
        return content
    return json.dumps(snapshots[-1], ensure_ascii=False, separators=(",", ":"))


def opentrek_message_metadata(provider: OpenTrekProviderConfig) -> dict[str, Any]:
    metadata: dict[str, Any] = {"source": "interview-guide"}
    if (
        provider.capability
        in {
            OpenTrekCapability.INTERVIEWER,
            OpenTrekCapability.EVALUATOR,
        }
        and provider.skill_names
    ):
        unknown = set(provider.skill_names).difference(OPENTREK_INTERVIEW_SKILLS)
        if unknown:
            raise BusinessException(
                ErrorCode.AI_SERVICE_ERROR,
                f"OpenTrek Skill 未发布：{sorted(unknown)[0]}",
            )
        metadata["skillList"] = list(provider.skill_names)
    return metadata
