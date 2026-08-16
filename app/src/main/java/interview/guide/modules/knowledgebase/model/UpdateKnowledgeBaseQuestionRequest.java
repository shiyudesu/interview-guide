package interview.guide.modules.knowledgebase.model;

import java.util.List;

public record UpdateKnowledgeBaseQuestionRequest(
    String difficulty,
    String type,
    String category,
    String question,
    String topicSummary,
    String referenceAnswer,
    List<String> keyPoints,
    String scoringRubric,
    List<KnowledgeBaseQuestionFollowUpDTO> followUps,
    String sourceContext,
    KnowledgeBaseQuestionStatus status
) {
}
