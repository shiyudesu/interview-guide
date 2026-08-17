from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from interview_guide.common.ai.adapter import LlmAdapter, ProviderConfig
from interview_guide.common.ai.prompts import ANTI_INJECTION_INSTRUCTION
from interview_guide.common.errors import BusinessException, ErrorCode

T = TypeVar("T", bound=BaseModel)
JAVA_FORMAT_PREFIX = "Your response should be in JSON format."

STRICT_JSON_INSTRUCTION = """请仅返回可被 JSON 解析器直接解析的 JSON 对象，并严格满足字段结构要求：
1) 不要输出 Markdown 代码块（如 ```json）。
2) 不要输出任何解释文字、前后缀、注释。
3) 所有字符串内引号必须正确转义。
"""


def java_schema_json(value: object, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = list(value.items())
        lines = ["{"]
        for index, (key, item) in enumerate(items):
            rendered = java_schema_json(item, indent + 2)
            lines.append(
                f"{' ' * (indent + 2)}{json.dumps(str(key), ensure_ascii=False)} : "
                f"{rendered}{',' if index + 1 < len(items) else ''}"
            )
        lines.append(f"{prefix}}}")
        return "\n".join(lines)
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return "[ " + ", ".join(java_schema_json(item) for item in value) + " ]"
        return (
            "[\n"
            + ",\n".join(
                f"{' ' * (indent + 2)}{java_schema_json(item, indent + 2)}" for item in value
            )
            + f"\n{prefix}]"
        )
    return json.dumps(value, ensure_ascii=False)


def java_bean_output_format(schema: dict[str, object]) -> str:
    return (
        f"{JAVA_FORMAT_PREFIX}\n"
        "Do not include any explanations, only provide a RFC8259 compliant JSON "
        "response following this format without deviation.\n"
        "Do not include markdown code blocks in your response.\n"
        "Remove the ```json markdown from the output.\n"
        "Here is the JSON Schema instance your output must adhere to:\n"
        f"```{java_schema_json(schema)}```\n"
    )


def repair_unescaped_quotes(content: str) -> str:
    if not content.strip():
        return content
    repaired: list[str] = []
    in_string = False
    escaping = False
    for index, character in enumerate(content):
        if not in_string:
            if character == '"':
                in_string = True
            repaired.append(character)
            continue
        if escaping:
            repaired.append(character)
            escaping = False
            continue
        if character == "\\":
            repaired.append(character)
            escaping = True
            continue
        if character == '"':
            if is_likely_json_string_terminator(content, index + 1):
                in_string = False
                repaired.append(character)
            else:
                repaired.append('\\"')
            continue
        repaired.append(character)
    return "".join(repaired)


def is_likely_json_string_terminator(content: str, start: int) -> bool:
    for character in content[start:]:
        if character.isspace():
            continue
        return character in {",", "}", "]", ":"}
    return True


class StructuredOutputInvoker:
    def __init__(
        self,
        adapter: LlmAdapter,
        *,
        max_attempts: int = 2,
        include_last_error: bool = True,
        use_repair_prompt: bool = True,
        append_strict_json_instruction: bool = True,
        error_message_max_length: int = 200,
    ) -> None:
        self._adapter = adapter
        self._max_attempts = max(1, max_attempts)
        self._include_last_error = include_last_error
        self._use_repair_prompt = use_repair_prompt
        self._append_strict_json_instruction = append_strict_json_instruction
        self._error_message_max_length = max(20, error_message_max_length)

    async def invoke(
        self,
        provider: ProviderConfig,
        system_prompt_with_format: str,
        user_prompt: str,
        output_type: type[T],
        error_code: ErrorCode,
        error_prefix: str,
        *,
        tools: Sequence[dict[str, object]] | None = None,
    ) -> T:
        secured_system_prompt = system_prompt_with_format + ANTI_INJECTION_INSTRUCTION
        format_start = system_prompt_with_format.find(JAVA_FORMAT_PREFIX)
        formatted_user_prompt = (
            user_prompt + "\n" + system_prompt_with_format[format_start:]
            if format_start >= 0
            else user_prompt
        )
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            system_prompt = (
                secured_system_prompt
                if attempt == 1
                else self._retry_prompt(secured_system_prompt, last_error)
            )
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": formatted_user_prompt},
                ]
                response = (
                    await self._adapter.chat(provider, messages, tools=tools)
                    if tools is not None
                    else await self._adapter.chat(provider, messages)
                )
                return self._convert(response.content or "", output_type)
            except Exception as error:
                last_error = error
        detail = str(last_error) if last_error is not None else "unknown"
        raise BusinessException(error_code, f"{error_prefix}{detail}")

    def _convert(self, content: str, output_type: type[T]) -> T:
        try:
            return output_type.model_validate_json(content)
        except ValidationError as first_error:
            repaired = repair_unescaped_quotes(content)
            if repaired != content:
                try:
                    return output_type.model_validate_json(repaired)
                except ValidationError as repair_error:
                    first_error.add_note(str(repair_error))
            raise first_error

    def _retry_prompt(
        self,
        system_prompt: str,
        last_error: Exception | None,
    ) -> str:
        if not self._use_repair_prompt:
            return system_prompt
        additions: list[str] = [system_prompt, ""]
        if self._append_strict_json_instruction:
            additions.append(STRICT_JSON_INSTRUCTION)
        additions.append("上次输出解析失败，请仅返回合法 JSON。")
        if self._include_last_error and last_error is not None:
            message = str(last_error).replace("\n", " ").replace("\r", " ").strip()
            if len(message) > self._error_message_max_length:
                message = f"{message[: self._error_message_max_length]}..."
            additions.append(f"上次失败原因：{message}")
        return "\n".join(additions)
