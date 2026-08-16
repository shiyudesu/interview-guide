package interview.guide.modules.interview.service;

import interview.guide.common.evaluation.EvaluationReport;
import interview.guide.common.evaluation.QaRecord;
import interview.guide.common.evaluation.UnifiedEvaluationService;
import interview.guide.common.exception.BusinessException;
import interview.guide.common.exception.ErrorCode;
import interview.guide.modules.interview.model.InterviewQuestionDTO;
import interview.guide.modules.interview.model.InterviewReportDTO;
import interview.guide.modules.interview.model.InterviewReportDTO.CategoryScore;
import interview.guide.modules.interview.model.InterviewReportDTO.QuestionEvaluation;
import interview.guide.modules.interview.model.InterviewReportDTO.ReferenceAnswer;
import interview.guide.modules.interview.skill.InterviewSkillService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 文字面试答案评估服务
 * 职责：DTO 适配器，将 InterviewQuestionDTO 转为通用 QaRecord，调用 UnifiedEvaluationService
 */
@Service
public class AnswerEvaluationService {

    private static final Logger log = LoggerFactory.getLogger(AnswerEvaluationService.class);

    private final UnifiedEvaluationService unifiedEvaluationService;
    private final InterviewPersistenceService persistenceService;
    private final InterviewSkillService skillService;

    public AnswerEvaluationService(UnifiedEvaluationService unifiedEvaluationService,
                                   InterviewPersistenceService persistenceService,
                                   InterviewSkillService skillService) {
        this.unifiedEvaluationService = unifiedEvaluationService;
        this.persistenceService = persistenceService;
        this.skillService = skillService;
    }

    /**
     * 评估完整面试并生成报告
     */
    public InterviewReportDTO evaluateInterview(ChatClient chatClient, String sessionId, String resumeText,
                                                 List<InterviewQuestionDTO> questions) {
        log.info("开始评估面试: {}, 共{}题", sessionId, questions.size());

        try {
            // 转为通用问答记录
            List<QaRecord> qaRecords = questions.stream()
                .map(q -> new QaRecord(q.questionIndex(), q.question(), q.category(), q.userAnswer()))
                .toList();

            String referenceContext = buildQuestionReferenceContext(questions);
            if (referenceContext.isBlank()) {
                referenceContext = skillService.buildEvaluationReferenceSectionSafe(
                    persistenceService.findBySessionId(sessionId)
                        .map(s -> s.getSkillId())
                        .orElse(null)
                );
            }

            // 调用通用评估服务
            EvaluationReport report = unifiedEvaluationService.evaluate(
                chatClient, sessionId, qaRecords, resumeText, referenceContext
            );

            // 转为文字面试专用 DTO
            return withQuestionReferences(toInterviewReportDTO(report), questions);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("面试评估失败: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INTERVIEW_EVALUATION_FAILED,
                "面试评估失败：" + e.getMessage());
        }
    }

    private InterviewReportDTO toInterviewReportDTO(EvaluationReport report) {
        return new InterviewReportDTO(
            report.sessionId(),
            report.totalQuestions(),
            report.overallScore(),
            report.categoryScores().stream()
                .map(cs -> new CategoryScore(cs.category(), cs.score(), cs.questionCount()))
                .toList(),
            report.questionDetails().stream()
                .map(qe -> new QuestionEvaluation(qe.questionIndex(), qe.question(), qe.category(),
                    qe.userAnswer(), qe.score(), qe.feedback()))
                .toList(),
            report.overallFeedback(),
            report.strengths(),
            report.improvements(),
            report.referenceAnswers().stream()
                .map(ra -> new ReferenceAnswer(ra.questionIndex(), ra.question(),
                    ra.referenceAnswer(), ra.keyPoints()))
                .toList()
        );
    }

    private InterviewReportDTO withQuestionReferences(InterviewReportDTO report,
                                                      List<InterviewQuestionDTO> questions) {
        List<InterviewReportDTO.ReferenceAnswer> references = report.referenceAnswers().stream()
            .map(reference -> {
                InterviewQuestionDTO question = questions.stream()
                    .filter(item -> item.questionIndex() == reference.questionIndex())
                    .findFirst()
                    .orElse(null);
                if (question == null || question.referenceAnswer() == null
                    || question.referenceAnswer().isBlank()) {
                    return reference;
                }
                return new InterviewReportDTO.ReferenceAnswer(
                    reference.questionIndex(),
                    reference.question(),
                    question.referenceAnswer(),
                    question.keyPoints() != null ? question.keyPoints() : List.of()
                );
            })
            .toList();
        return new InterviewReportDTO(
            report.sessionId(),
            report.totalQuestions(),
            report.overallScore(),
            report.categoryScores(),
            report.questionDetails(),
            report.overallFeedback(),
            report.strengths(),
            report.improvements(),
            references
        );
    }

    private String buildQuestionReferenceContext(List<InterviewQuestionDTO> questions) {
        StringBuilder sb = new StringBuilder();
        for (InterviewQuestionDTO question : questions) {
            if (!hasQuestionReference(question)) {
                continue;
            }
            sb.append("问题").append(question.questionIndex() + 1).append(": ")
                .append(question.question()).append('\n');
            appendIfPresent(sb, "参考答案", question.referenceAnswer());
            if (question.keyPoints() != null && !question.keyPoints().isEmpty()) {
                sb.append("评分要点: ").append(String.join("；", question.keyPoints())).append('\n');
            }
            appendIfPresent(sb, "评分规则", question.scoringRubric());
            sb.append('\n');
        }
        return sb.toString();
    }

    private boolean hasQuestionReference(InterviewQuestionDTO question) {
        return hasText(question.referenceAnswer())
            || hasText(question.scoringRubric())
            || (question.keyPoints() != null && !question.keyPoints().isEmpty());
    }

    private void appendIfPresent(StringBuilder sb, String label, String value) {
        if (hasText(value)) {
            sb.append(label).append(": ").append(value.trim()).append('\n');
        }
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
