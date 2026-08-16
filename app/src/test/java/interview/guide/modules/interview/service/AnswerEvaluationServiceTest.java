package interview.guide.modules.interview.service;

import interview.guide.common.evaluation.EvaluationReport;
import interview.guide.common.evaluation.UnifiedEvaluationService;
import interview.guide.modules.interview.model.InterviewQuestionDTO;
import interview.guide.modules.interview.model.InterviewReportDTO;
import interview.guide.modules.interview.skill.InterviewSkillService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AnswerEvaluationServiceTest {

  @Mock
  private UnifiedEvaluationService unifiedEvaluationService;

  @Mock
  private InterviewPersistenceService persistenceService;

  @Mock
  private InterviewSkillService skillService;

  @Test
  @DisplayName("题目自带评分依据时不再拼接 Skill 参考基线")
  void shouldSkipSkillReferenceWhenQuestionsHaveReferences() {
    AnswerEvaluationService service = new AnswerEvaluationService(
        unifiedEvaluationService,
        persistenceService,
        skillService
    );
    InterviewQuestionDTO question = InterviewQuestionDTO.fromQuestionBank(
        0,
        "什么是索引下推？",
        "MYSQL",
        "MySQL",
        "索引优化",
        "参考答案",
        List.of("评分要点"),
        "评分规则",
        "来源片段"
    );
    when(unifiedEvaluationService.evaluate(
        nullable(ChatClient.class), eq("session1"), any(), eq("简历"), any()
    )).thenReturn(report());

    InterviewReportDTO actual = service.evaluateInterview(null, "session1", "简历", List.of(question));

    ArgumentCaptor<String> referenceCaptor = ArgumentCaptor.forClass(String.class);
    verify(unifiedEvaluationService).evaluate(
        nullable(ChatClient.class), eq("session1"), any(), eq("简历"), referenceCaptor.capture()
    );
    verify(skillService, never()).buildEvaluationReferenceSectionSafe(any());
    verify(persistenceService, never()).findBySessionId(any());
    assertThat(referenceCaptor.getValue())
        .contains("参考答案")
        .contains("评分要点")
        .contains("评分规则")
        .doesNotContain("来源片段");
    assertThat(actual.referenceAnswers().getFirst().referenceAnswer()).isEqualTo("参考答案");
  }

  private EvaluationReport report() {
    return new EvaluationReport(
        "session1",
        1,
        80,
        List.of(new EvaluationReport.CategoryScore("MySQL", 80, 1)),
        List.of(new EvaluationReport.QuestionEvaluation(
            0,
            "什么是索引下推？",
            "MySQL",
            "回答",
            80,
            "不错"
        )),
        "整体不错",
        List.of("基础扎实"),
        List.of("继续深入"),
        List.of(new EvaluationReport.ReferenceAnswer(
            0,
            "什么是索引下推？",
            "模型参考",
            List.of("模型要点")
        ))
    );
  }
}
