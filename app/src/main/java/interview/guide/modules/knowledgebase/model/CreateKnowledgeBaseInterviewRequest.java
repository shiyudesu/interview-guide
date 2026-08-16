package interview.guide.modules.knowledgebase.model;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record CreateKnowledgeBaseInterviewRequest(
    @NotNull(message = "知识库不能为空")
    Long knowledgeBaseId,
    // 面试方向，可空。为空表示覆盖知识库内所有方向的已启用题目。
    String category,
    String difficulty,
    @Min(value = 1, message = "主问题数量最少1题")
    @Max(value = 20, message = "主问题数量最多20题")
    int mainQuestionCount,
    @Min(value = 0, message = "追问数量不能小于0")
    @Max(value = 5, message = "每题追问最多5个")
    int followUpCount,
    String llmProvider
) {
}
