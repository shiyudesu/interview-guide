package interview.guide.modules.knowledgebase.model;

import java.util.List;

/**
 * 知识库面试在指定方向、难度和主问题数下的可用容量。
 */
public record KnowledgeBaseInterviewCapacityResponse(
    Long knowledgeBaseId,
    String category,
    String difficulty,
    int mainQuestionCount,
    List<CategoryOption> categories,
    List<FollowUpOption> followUpOptions
) {

  public record CategoryOption(
      String category,
      int availableQuestionCount
  ) {
  }

  public record FollowUpOption(
      int followUpCount,
      int availableQuestionCount,
      boolean selectable
  ) {
  }
}
