package interview.guide.modules.knowledgebase.model;

import jakarta.validation.constraints.NotBlank;

import java.util.List;

public record CreateKnowledgeBaseQuestionRequest(
    String difficulty,
    String type,
    @NotBlank(message = "面试方向不能为空")
    String category,
    @NotBlank(message = "题干不能为空")
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
