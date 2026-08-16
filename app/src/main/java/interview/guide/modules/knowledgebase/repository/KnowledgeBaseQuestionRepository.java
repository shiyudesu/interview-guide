package interview.guide.modules.knowledgebase.repository;

import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionEntity;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface KnowledgeBaseQuestionRepository extends JpaRepository<KnowledgeBaseQuestionEntity, Long> {

  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdOrderByUpdatedAtDesc(Long knowledgeBaseId);

  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndStatusOrderByUpdatedAtDesc(
      Long knowledgeBaseId, KnowledgeBaseQuestionStatus status);

  List<KnowledgeBaseQuestionEntity> findTop50ByKnowledgeBase_IdAndSkillIdAndDifficultyOrderByUpdatedAtDesc(
      Long knowledgeBaseId, String skillId, String difficulty);

  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndSkillIdAndDifficultyAndStatusOrderByUpdatedAtDesc(
      Long knowledgeBaseId,
      String skillId,
      String difficulty,
      KnowledgeBaseQuestionStatus status
  );

  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndSkillIdAndDifficulty(Long knowledgeBaseId,
                                                                                    String skillId,
                                                                                    String difficulty);

  /**
   * 同知识库内按难度筛选的题目（不限定 skillId，因为知识库题目 skillId 都是默认值）。
   */
  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndDifficulty(Long knowledgeBaseId, String difficulty);

  List<KnowledgeBaseQuestionEntity> findTop20ByKnowledgeBase_IdAndDifficultyOrderByUpdatedAtDesc(
      Long knowledgeBaseId, String difficulty);

  /**
   * 同知识库 + 难度 + 方向（category）下的已启用题目，用于开始知识库面试抽题。
   */
  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndDifficultyAndCategoryAndStatusOrderByUpdatedAtDesc(
      Long knowledgeBaseId,
      String difficulty,
      String category,
      KnowledgeBaseQuestionStatus status
  );

  /**
   * 同知识库 + 难度下的已启用题目，category 为空时表示覆盖所有方向。
   */
  List<KnowledgeBaseQuestionEntity> findByKnowledgeBase_IdAndDifficultyAndStatusOrderByUpdatedAtDesc(
      Long knowledgeBaseId,
      String difficulty,
      KnowledgeBaseQuestionStatus status
  );

  /**
   * 列出某知识库下出现过的方向（含计数），用于前端下拉。
   * 只统计有非空 category 的题目，按出现次数降序。
   */
  @Query("select q.category as category, count(q) as count "
      + "from KnowledgeBaseQuestionEntity q "
      + "where q.knowledgeBase.id = :kbId and q.category is not null and q.category <> '' "
      + "group by q.category order by count(q) desc, q.category asc")
  List<CategoryCount> findCategoryCounts(@Param("kbId") Long knowledgeBaseId);

  interface CategoryCount {
    String getCategory();

    Long getCount();
  }

  /**
   * 删除某知识库下的所有题目（用于重新生成时替换）
   */
  @Modifying
  @Query("DELETE FROM KnowledgeBaseQuestionEntity q WHERE q.knowledgeBase.id = :kbId")
  int deleteByKnowledgeBaseId(@Param("kbId") Long knowledgeBaseId);
}
