package interview.guide.modules.interview.model;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SessionListItemDTOTest {

  @Test
  @DisplayName("from 映射知识库面试方向字段")
  void shouldMapInterviewCategory() {
    InterviewSessionEntity entity = new InterviewSessionEntity();
    entity.setSessionId("s1");
    entity.setSourceType("KNOWLEDGE_BASE");
    entity.setKnowledgeBaseId(1L);
    entity.setInterviewCategory("MySQL");
    entity.setTotalQuestions(5);

    SessionListItemDTO dto = SessionListItemDTO.from(entity);

    assertThat(dto.interviewCategory()).isEqualTo("MySQL");
    assertThat(dto.sourceType()).isEqualTo("KNOWLEDGE_BASE");
    assertThat(dto.knowledgeBaseId()).isEqualTo(1L);
  }

  @Test
  @DisplayName("历史普通面试记录的 interviewCategory 为 null 时正常映射")
  void shouldMapNullInterviewCategory() {
    InterviewSessionEntity entity = new InterviewSessionEntity();
    entity.setSessionId("s2");
    entity.setTotalQuestions(null);

    SessionListItemDTO dto = SessionListItemDTO.from(entity);

    assertThat(dto.interviewCategory()).isNull();
    assertThat(dto.totalQuestions()).isZero();
  }
}
