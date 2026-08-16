package interview.guide.modules.voiceinterview.service;

import interview.guide.common.ai.LlmProviderRegistry;
import interview.guide.common.evaluation.UnifiedEvaluationService;
import interview.guide.modules.interview.skill.InterviewSkillService;
import interview.guide.modules.voiceinterview.model.VoiceInterviewEvaluationEntity;
import interview.guide.modules.voiceinterview.model.VoiceInterviewSessionEntity;
import interview.guide.modules.voiceinterview.repository.VoiceInterviewEvaluationRepository;
import interview.guide.modules.voiceinterview.repository.VoiceInterviewMessageRepository;
import interview.guide.modules.voiceinterview.repository.VoiceInterviewSessionRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("语音面试评估服务")
class VoiceInterviewEvaluationServiceTest {

    @Mock
    private UnifiedEvaluationService unifiedEvaluationService;

    @Mock
    private LlmProviderRegistry llmProviderRegistry;

    @Mock
    private VoiceInterviewEvaluationRepository evaluationRepository;

    @Mock
    private VoiceInterviewMessageRepository messageRepository;

    @Mock
    private VoiceInterviewSessionRepository sessionRepository;

    @Mock
    private ObjectMapper objectMapper;

    @Mock
    private InterviewSkillService skillService;

    @InjectMocks
    private VoiceInterviewEvaluationService evaluationService;

    @Test
    @DisplayName("没有有效对话时应显示暂无评分而不是零分")
    void shouldNotAssignZeroScoreWhenNoConversationExists() {
        VoiceInterviewSessionEntity session = VoiceInterviewSessionEntity.builder()
            .id(1L)
            .roleType("Java 后端开发")
            .startTime(LocalDateTime.now())
            .build();
        when(evaluationRepository.findBySessionId(1L)).thenReturn(Optional.empty());

        evaluationService.saveEmptyEvaluationTransactional(1L, session);

        ArgumentCaptor<VoiceInterviewEvaluationEntity> captor =
            ArgumentCaptor.forClass(VoiceInterviewEvaluationEntity.class);
        verify(evaluationRepository).save(captor.capture());
        assertThat(captor.getValue().getOverallScore()).isNull();
        assertThat(captor.getValue().getOverallFeedback()).contains("暂无可评估内容");
    }
}
