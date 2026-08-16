package interview.guide.modules.voiceinterview.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Voice evaluation status response DTO
 * 语音面试评估状态响应
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VoiceEvaluationStatusDTO {

    /**
     * Evaluation task status: PENDING / PROCESSING / COMPLETED / FAILED
     */
    private String evaluateStatus;

    /**
     * Error message when status is FAILED
     */
    private String evaluateError;

    /**
     * Time when the current evaluation status was last updated.
     */
    private LocalDateTime evaluateStatusUpdatedAt;

    /**
     * Full evaluation result, only present when status is COMPLETED
     */
    private VoiceEvaluationDetailDTO evaluation;
}
