from __future__ import annotations

from interview_guide.modules.knowledge_base.question_models import (
    CreateKnowledgeBaseInterviewRequest,
)


def test_knowledge_base_follow_up_count_is_dynamic_limit() -> None:
    request = CreateKnowledgeBaseInterviewRequest(
        knowledgeBaseId=1,
        difficulty="mid",
        mainQuestionCount=5,
        followUpCount=3,
        requestId="kb_request_123",
    )
    assert request.follow_up_count == 3
    assert request.request_id == "kb_request_123"
