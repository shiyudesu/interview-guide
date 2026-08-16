package interview.guide.modules.knowledgebase.model;

/**
 * 知识库题目生成参数快照。
 */
public record QuestionGenerationConfig(
    String difficulty,
    int questionCount,
    int followUpCount,
    int categoryLimit,
    String llmProvider
) {
}
