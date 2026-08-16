package interview.guide.modules.knowledgebase.model;

import java.util.List;

public record KnowledgeBaseQuestionFollowUpDTO(
    String question,
    String referenceAnswer,
    List<String> keyPoints,
    String scoringRubric
) {
  public KnowledgeBaseQuestionFollowUpDTO(String question) {
    this(question, null, List.of(), null);
  }
}
