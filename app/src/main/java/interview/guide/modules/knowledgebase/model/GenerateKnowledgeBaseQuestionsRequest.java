package interview.guide.modules.knowledgebase.model;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record GenerateKnowledgeBaseQuestionsRequest(
    @Pattern(regexp = "junior|mid|senior", message = "题目难度不合法")
    String difficulty,
    @Min(value = 1, message = "题目数量最少1题")
    @Max(value = 30, message = "题目数量最多30题")
    int questionCount,
    @Min(value = 0, message = "追问数量不能小于0")
    @Max(value = 5, message = "每题追问最多5个")
    Integer followUpCount,
    @Min(value = 1, message = "方向数最少1个")
    @Max(value = 5, message = "方向数最多5个")
    @NotNull(message = "方向数量不能为空")
    Integer categoryLimit,
    @Size(max = 64, message = "模型提供商标识过长")
    String llmProvider
) {
}
