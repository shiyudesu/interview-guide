package interview.guide.modules.interview.model;

import interview.guide.common.model.AsyncTaskStatus;

import java.time.LocalDateTime;

/**
 * 面试历史列表项 DTO（用于简历详情页展示关联面试记录）
 */
public record InterviewHistoryItemDTO(
    Long id,
    String sessionId,
    Integer totalQuestions,
    String status,
    String evaluateStatus,
    String evaluateError,
    Integer overallScore,
    LocalDateTime createdAt,
    LocalDateTime completedAt
) {}
