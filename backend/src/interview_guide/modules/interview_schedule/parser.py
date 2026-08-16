from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from interview_guide.common.ai.adapter import LlmAdapter
from interview_guide.common.ai.prompts import (
    DATA_BOUNDARY_INSTRUCTION,
    PromptSanitizer,
)
from interview_guide.common.ai.providers import LlmProviderRegistry
from interview_guide.modules.interview_schedule.models import (
    CreateInterviewRequest,
    ParseResponse,
)

logger = logging.getLogger(__name__)

CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
TIME_FEISHU = re.compile(r"(?:时间|时段)[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})")
LINK_FEISHU = re.compile(r"https://meeting\.feishu\.cn/[^\s\n]+")
COMPANY_FEISHU = re.compile(r"(?:公司|单位|组织)[：:]\s*([^\s\n]{1,50})")
POSITION_FEISHU = re.compile(r"(?:岗位|职位|职务)[：:]\s*([^\s\n]{1,50})")
ROUND_FEISHU = re.compile(r"第\s*[一二三四五六七八九十\d]+\s*[轮场]")

TIME_TENCENT = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})\s+(\d{2}:\d{2})")
MEETING_ID_TENCENT = re.compile(r"(?:会议号|ID)[：:]?\s*(\d{9,})")
PASSWORD_TENCENT = re.compile(r"密码[：:]?\s*(\d{4,})")
COMPANY_TENCENT = re.compile(r"(?:公司|单位)[：:]\s*([^\s\n]{1,50})")
POSITION_TENCENT = re.compile(r"(?:岗位|职位)[：:]\s*([^\s\n]{1,50})")

LINK_ZOOM = re.compile(r"https://zoom\.us/j/[^\s\n]+")
DATE_ZOOM = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})")
HOUR_ZOOM = re.compile(r"(\d{1,2}:\d{2})")
ROUND_NUMBER = re.compile(r"[一二三四五六七八九十]|\d")
CODE_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")

PARSE_PROMPT = """你是一个专业的面试邀约信息提取助手。请仔细分析以下文本，提取面试相关信息。

**提取规则**：
1. companyName（公司名称）：提取面试公司的全称或简称，**必需字段**
2. position（岗位名称）：提取面试岗位的名称，**必需字段**
3. interviewTime（面试时间）：提取面试开始时间并转换为 ISO 8601 格式，**必需字段**
   - 格式：YYYY-MM-DDTHH:MM:SS（例如：2026-04-10T14:00:00）
   - 若只有相对时间（如"明天下午2点"），根据当前日期 %s 推算
4. interviewType（面试形式）：ONSITE（现场）/ VIDEO（视频）/ PHONE（电话）
5. meetingLink（会议链接）：提取完整的会议链接或会议号+密码
6. roundNumber（第几轮面试）：提取数字（1-10），如"二面"提取为2
7. notes（其他备注）：包含面试官姓名（如果不重要可忽略）、时长（**默认30分钟**）等。

**重要提示**：
- 面试官是谁不重要，只需在 notes 中提及。
- 优先保证 companyName、position、interviewTime 的准确性。
- 如果文本中没说时长，默认设置为 30 分钟。

**待解析文本**：
%s

**返回格式**：
纯 JSON 格式，不要包含```json标记，示例：
{"companyName":"阿里巴巴","position":"Java工程师","interviewTime":"2026-04-10T14:00:00","interviewType":"VIDEO","meetingLink":"https://meeting.feishu.cn/xxx","roundNumber":2,"interviewer":"张三","notes":"技术面"}
"""


@dataclass
class ParsedSchedule:
    company_name: str | None = None
    position: str | None = None
    interview_time: datetime | None = None
    interview_type: str | None = None
    meeting_link: str | None = None
    round_number: int | None = 1
    interviewer: str | None = None
    notes: str | None = None

    def valid(self) -> bool:
        return (
            self.company_name is not None
            and self.position is not None
            and self.interview_time is not None
        )

    def request(self) -> CreateInterviewRequest:
        if not self.valid():
            raise ValueError("Parsed schedule is incomplete")
        return CreateInterviewRequest(
            company_name=self.company_name,
            position=self.position,
            interview_time=self.interview_time,
            interview_type=self.interview_type,
            meeting_link=self.meeting_link,
            round_number=self.round_number,
            interviewer=self.interviewer,
            notes=self.notes,
        )


class InterviewParseService:
    def __init__(
        self,
        registry: LlmProviderRegistry,
        adapter: LlmAdapter,
        sanitizer: PromptSanitizer,
        now: datetime,
    ) -> None:
        self._registry = registry
        self._adapter = adapter
        self._sanitizer = sanitizer
        self._now = now

    async def parse(self, raw_text: str, source: str | None) -> ParseResponse:
        if not raw_text.strip():
            return ParseResponse(
                confidence=0,
                data=None,
                log="输入文本为空",
                parse_method="none",
                success=False,
            )
        result = self._try_rules(raw_text, source)
        if result.valid():
            return ParseResponse(
                confidence=0.95,
                data=result.request(),
                log="规则解析成功",
                parse_method="rule",
                success=True,
            )
        ai_result = await self._parse_ai(raw_text, source)
        if ai_result is not None and ai_result.valid():
            return ParseResponse(
                confidence=0.8,
                data=ai_result.request(),
                log="AI 解析成功",
                parse_method="ai",
                success=True,
            )
        return ParseResponse(
            confidence=0,
            data=None,
            log="解析失败",
            parse_method="none",
            success=False,
        )

    def _try_rules(self, raw_text: str, source: str | None) -> ParsedSchedule:
        normalized = source.lower() if source is not None else None
        if normalized == "feishu":
            return self._parse_feishu(raw_text)
        if normalized == "tencent":
            return self._parse_tencent(raw_text)
        if normalized == "zoom":
            return self._parse_zoom(raw_text)
        if any(marker in raw_text for marker in ("飞书", "Feishu", "meeting.feishu.cn")):
            result = self._parse_feishu(raw_text)
            if result.valid():
                return result
        if any(marker in raw_text for marker in ("腾讯会议", "Tencent Meeting", "会议号")):
            result = self._parse_tencent(raw_text)
            if result.valid():
                return result
        if "Zoom" in raw_text or "zoom.us" in raw_text:
            result = self._parse_zoom(raw_text)
            if result.valid():
                return result
        for parser in (
            self._parse_feishu,
            self._parse_tencent,
            self._parse_zoom,
        ):
            result = parser(raw_text)
            if result.valid() or parser is self._parse_zoom:
                return result
        return ParsedSchedule()

    def _parse_feishu(self, raw_text: str) -> ParsedSchedule:
        result = ParsedSchedule()
        try:
            if match := TIME_FEISHU.search(raw_text):
                result.interview_time = parse_datetime(match.group(1))
            if match := LINK_FEISHU.search(raw_text):
                result.meeting_link = match.group(0)
            if match := COMPANY_FEISHU.search(raw_text):
                result.company_name = match.group(1).strip()
            if match := POSITION_FEISHU.search(raw_text):
                result.position = match.group(1).strip()
            if match := ROUND_FEISHU.search(raw_text):
                result.round_number = parse_round_number(match.group(0))
            result.interview_type = "VIDEO"
        except Exception:
            logger.exception("Feishu rule parsing failed")
        return result

    def _parse_tencent(self, raw_text: str) -> ParsedSchedule:
        result = ParsedSchedule()
        try:
            if match := TIME_TENCENT.search(raw_text):
                result.interview_time = parse_datetime(f"{match.group(1)} {match.group(2)}")
            meeting_link = ""
            if match := MEETING_ID_TENCENT.search(raw_text):
                meeting_link += f"会议号: {match.group(0)}"
            if match := PASSWORD_TENCENT.search(raw_text):
                meeting_link += f" 密码: {match.group(0)}"
            if meeting_link:
                result.meeting_link = meeting_link
            if match := COMPANY_TENCENT.search(raw_text):
                result.company_name = match.group(1).strip()
            if match := POSITION_TENCENT.search(raw_text):
                result.position = match.group(1).strip()
            result.interview_type = "VIDEO"
        except Exception:
            logger.exception("Tencent rule parsing failed")
        return result

    def _parse_zoom(self, raw_text: str) -> ParsedSchedule:
        result = ParsedSchedule()
        try:
            if match := LINK_ZOOM.search(raw_text):
                result.meeting_link = match.group(0)
            date = DATE_ZOOM.search(raw_text)
            hour = HOUR_ZOOM.search(raw_text)
            if date is not None and hour is not None:
                result.interview_time = parse_datetime(f"{date.group(1)} {hour.group(1)}")
            result.interview_type = "VIDEO"
        except Exception:
            logger.exception("Zoom rule parsing failed")
        return result

    async def _parse_ai(
        self,
        raw_text: str,
        provider_id: str | None,
    ) -> ParsedSchedule | None:
        try:
            safe_text = self._sanitizer.sanitize(raw_text) or ""
            boundary = self._sanitizer.wrap_with_delimiters(
                "parse-input",
                safe_text,
            )
            prompt = PARSE_PROMPT % (
                self._now.date().isoformat(),
                f"{DATA_BOUNDARY_INSTRUCTION}\n{boundary}",
            )
            provider = await self._registry.get_chat(provider_id)
            response = await self._adapter.chat(
                provider,
                [{"role": "user", "content": prompt}],
            )
            if response.content is None or not response.content.strip():
                return None
            content = response.content.strip()
            if "```" in content and (match := CODE_BLOCK.search(content)):
                content = match.group(1).strip()
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or not parsed:
                return None
            return parsed_schedule_from_ai(parsed)
        except Exception:
            logger.exception("AI interview schedule parsing failed")
            return None


def parse_datetime(value: str) -> datetime | None:
    normalized = value.replace("/", "-")
    try:
        if len(normalized) == 16:
            return datetime.strptime(normalized, "%Y-%m-%d %H:%M")
        if len(normalized) == 19:
            return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_round_number(text: str | None) -> int:
    if text is None:
        return 1
    normalized = text.strip()
    if normalized.isdigit():
        return int(normalized)
    match = ROUND_NUMBER.search(normalized)
    if match is None:
        return 1
    value = match.group(0)
    default_value = int(re.sub(r"\D", "", value))
    return CHINESE_NUMBERS.get(value, default_value)


def parsed_schedule_from_ai(value: dict[str, Any]) -> ParsedSchedule:
    result = ParsedSchedule()
    if value.get("companyName") is not None:
        result.company_name = str(value["companyName"]).strip()
    if value.get("position") is not None:
        result.position = str(value["position"]).strip()
    if value.get("interviewTime") is not None:
        time_value = str(value["interviewTime"]).strip()
        try:
            result.interview_time = datetime.fromisoformat(
                f"{time_value}:00" if len(time_value) == 16 else time_value
            )
        except ValueError:
            result.interview_time = None
    if value.get("interviewType") is not None:
        result.interview_type = str(value["interviewType"]).strip()
    if value.get("meetingLink") is not None:
        result.meeting_link = str(value["meetingLink"]).strip()
    if value.get("roundNumber") is not None:
        try:
            result.round_number = int(str(value["roundNumber"]).strip())
        except ValueError:
            result.round_number = 1
    if value.get("interviewer") is not None:
        result.interviewer = str(value["interviewer"]).strip()
    if value.get("notes") is not None:
        result.notes = str(value["notes"]).strip()
    return result
