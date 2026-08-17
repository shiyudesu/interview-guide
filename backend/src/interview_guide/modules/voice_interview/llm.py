from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from interview_guide.common.ai.adapter import LlmAdapter
from interview_guide.common.ai.prompts import (
    ANTI_INJECTION_INSTRUCTION,
    PromptSanitizer,
)
from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.db.models import VoiceInterviewSession
from interview_guide.modules.voice_interview.context import VoiceContextCompressor
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository

VOICE_RESPONSE_CONSTRAINTS = """
【语音面试输出约束】
1. 每轮只问 1 个主问题，必要时最多补 1 个短追问。
2. 总长度控制在 2-4 句，避免长段落、列表、Markdown、代码块。
3. 不要重复开场白，不要复述上一轮已问过的完整问题。
4. 若候选人回答过短或含糊，直接追问一个具体的技术细节或给出提示引导，不要简单确认后停止。
5. 当候选人明确要求换题时，立即切换到新的技术方向，不要停留在当前话题。
6. 语气简洁直接，适配口语对话。
""".strip()
MAX_TOOL_ROUNDS = 3


class UnifiedVoiceLlmStreamer:
    def __init__(
        self,
        repository: VoiceInterviewRepository,
        registry: LlmProviderRegistry,
        adapter: LlmAdapter,
        sanitizer: PromptSanitizer,
        skills: SkillRepository,
        compressor: VoiceContextCompressor,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._adapter = adapter
        self._sanitizer = sanitizer
        self._skills = skills
        self._compressor = compressor

    async def stream(
        self,
        session: VoiceInterviewSession,
        user_input: str,
    ) -> AsyncIterator[str]:
        provider = await self._registry.get_chat(session.llm_provider)
        history = await self._history(session)
        system = await self._system_prompt(session)
        prompt: list[str] = []
        if history:
            prompt.extend(("【之前的对话】", *history, "", "【当前对话】"))
        prompt.append(
            "用户："
            + self._sanitizer.wrap_with_delimiters(
                "input",
                self._sanitizer.sanitize(user_input) or "",
            )
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(prompt)},
        ]
        tools = (self._skills.tool_definition(),)
        for _ in range(MAX_TOOL_ROUNDS):
            tool_calls: dict[int, dict[str, str]] = {}
            async for event in self._adapter.stream_chat(
                provider,
                messages,
                tools=tools,
                tool_choice="auto",
            ):
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0]
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content
                self._merge_tool_calls(tool_calls, delta.get("tool_calls"))
            if not tool_calls:
                return
            ordered = [tool_calls[index] for index in sorted(tool_calls)]
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                        for call in ordered
                    ],
                }
            )
            for call in ordered:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": self._execute_tool(call),
                    }
                )

    async def _history(self, session: VoiceInterviewSession) -> list[str]:
        turns = await self._repository.messages(session.id)
        summary_row = await self._repository.summary_row(session.id)
        cached_summary = summary_row.ai_generated_text if summary_row is not None else None
        covered_turns = (
            max(0, -(summary_row.sequence_num or 0) - 1) if summary_row is not None else 0
        )
        compressed = await self._compressor.compress(
            turns,
            cached_summary,
            covered_turns,
            session.llm_provider,
        )
        if compressed.changed and compressed.summary:
            await self._repository.save_summary(
                session.id,
                compressed.summary,
                compressed.covered_turns,
            )
        history: list[str] = []
        if compressed.summary:
            history.append(f"【对话摘要】{compressed.summary}")
        history.extend(self._compressor.format_recent(compressed.recent))
        return history

    async def _system_prompt(self, session: VoiceInterviewSession) -> str:
        parts: list[str] = []
        skill_id = session.skill_id or ""
        if skill_id:
            parts.append(
                f"你是一位 {skill_id} 方向的面试官。\n"
                "如果尚未加载完整的角色设定，请调用 Skill 工具"
                f"（command: {skill_id}）加载该技能的 SKILL.md。\n"
                "工具输出包含完整的面试官角色和出题规则，后续对话应基于该角色进行。"
            )
        parts.append(VOICE_RESPONSE_CONSTRAINTS)
        resume_text = await self._repository.resume_text(session.resume_id)
        if resume_text:
            parts.extend(
                (
                    "【实时语音面试 - 候选人简历内容】",
                    "你已查阅过候选人简历。首轮仅用一句话说明已查阅，并立即进入首个问题。",
                    "【简历解析文本】",
                    self._sanitizer.wrap_with_delimiters(
                        "resume",
                        self._sanitizer.sanitize(resume_text) or "",
                    ),
                )
            )
        parts.append(ANTI_INJECTION_INSTRUCTION)
        return "\n\n".join(parts)

    @staticmethod
    def _merge_tool_calls(
        calls: dict[int, dict[str, str]],
        fragments: Any,
    ) -> None:
        if not isinstance(fragments, list):
            return
        for raw in fragments:
            if not isinstance(raw, dict):
                continue
            index = int(raw.get("index", 0))
            call = calls.setdefault(
                index,
                {"id": "", "name": "", "arguments": ""},
            )
            call_id = raw.get("id")
            if isinstance(call_id, str):
                call["id"] += call_id
            function = raw.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if isinstance(name, str):
                call["name"] += name
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                call["arguments"] += arguments

    def _execute_tool(self, call: dict[str, str]) -> str:
        if call["name"] != "Skill":
            return f"Unsupported tool: {call['name']}"
        try:
            arguments = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            return "Skill command arguments are invalid"
        command = arguments.get("command") if isinstance(arguments, dict) else None
        if not isinstance(command, str):
            return "Skill command is required"
        try:
            skill = self._skills.get(command)
        except Exception as error:
            return str(error)
        return skill.persona
