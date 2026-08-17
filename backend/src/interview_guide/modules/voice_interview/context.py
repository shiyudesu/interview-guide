from __future__ import annotations

import logging
from dataclasses import dataclass

from interview_guide.common.ai.adapter import LlmAdapter
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import VoiceInterviewMessage
from interview_guide.modules.voice_interview.repository import trim_to_none

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompressedHistory:
    summary: str | None
    recent: list[VoiceInterviewMessage]
    covered_turns: int
    changed: bool


class VoiceContextCompressor:
    def __init__(
        self,
        registry: LlmProviderRegistry,
        adapter: LlmAdapter,
        prompts: PromptRepository,
        settings: Settings,
    ) -> None:
        self._registry = registry
        self._adapter = adapter
        self._prompts = prompts
        self._settings = settings

    async def compress(
        self,
        turns: list[VoiceInterviewMessage],
        cached_summary: str | None,
        covered_turns: int,
        provider_id: str | None,
    ) -> CompressedHistory:
        mode = self._settings.voice_context_compression_mode.upper()
        window = self._settings.voice_context_compression_window_size
        if (
            not self._settings.voice_context_compression_enabled
            or mode == "NONE"
            or len(turns) <= window
        ):
            return CompressedHistory(None, turns, len(turns), False)

        total = len(turns)
        early_count = total - window
        summary = cached_summary
        changed = False
        effective_covered = (
            0 if trim_to_none(cached_summary) is None else min(max(covered_turns, 0), early_count)
        )
        if (
            mode == "SUMMARY"
            and early_count > effective_covered
            and early_count - effective_covered
            >= self._settings.voice_context_compression_summary_batch_size
        ):
            new_summary = await self._summarize(
                cached_summary,
                self.format_recent(turns[effective_covered:early_count]),
                provider_id,
            )
            if new_summary is not None and new_summary != cached_summary:
                summary = new_summary
                effective_covered = early_count
                changed = True
            else:
                summary = new_summary if new_summary is not None else cached_summary

        recent_start = effective_covered if mode == "SUMMARY" else early_count
        return CompressedHistory(
            summary,
            turns[recent_start:],
            effective_covered,
            changed,
        )

    @staticmethod
    def format_recent(turns: list[VoiceInterviewMessage]) -> list[str]:
        history: list[str] = []
        pending_ai: str | None = None
        for message in turns:
            ai_text = trim_to_none(message.ai_generated_text)
            user_text = trim_to_none(message.user_recognized_text)
            if pending_ai is not None:
                history.append(f"面试官：{pending_ai}")
                pending_ai = None
                if user_text is not None:
                    history.append(f"候选人：{user_text}")
                if ai_text is not None:
                    pending_ai = ai_text
                continue
            if ai_text is not None and user_text is not None:
                history.append(f"面试官：{ai_text}")
                history.append(f"候选人：{user_text}")
            elif ai_text is not None:
                pending_ai = ai_text
            elif user_text is not None:
                history.append(f"候选人：{user_text}")
        if pending_ai is not None:
            history.append(f"面试官：{pending_ai}")
        return history

    async def _summarize(
        self,
        previous_summary: str | None,
        early_turns: list[str],
        provider_id: str | None,
    ) -> str | None:
        if not early_turns:
            return previous_summary
        try:
            prompt = self._prompts.render(
                "voice-interview-context-summary.st",
                {
                    "previousSummary": previous_summary or "(空)",
                    "newTurns": "\n".join(early_turns),
                },
            )
            provider = await self._registry.get_chat(provider_id)
            result = await self._adapter.chat(
                provider,
                [{"role": "user", "content": prompt}],
            )
            return (
                result.content.strip()
                if result.content is not None and result.content.strip()
                else previous_summary
            )
        except Exception:
            logger.warning(
                "voice context summary failed; preserving existing summary",
                exc_info=True,
            )
            return previous_summary
