package interview.guide.modules.interview.model;

import java.util.List;

/**
 * 面试问题DTO
 * type 由 Skill category key 驱动（如 MYSQL、CSS、DYNAMIC_PROGRAMMING 等），不再使用枚举
 */
public record InterviewQuestionDTO(
    int questionIndex,
    String question,
    String type,           // Skill category key，如 "MYSQL"、"CSS"、"DP"
    String category,       // 展示用标签，如 "MySQL"、"CSS"、"动态规划"
    String topicSummary,   // 知识点摘要，如 "Redis RDB/AOF 持久化对比"，用于历史去重压缩
    String userAnswer,
    Integer score,
    String feedback,
    boolean isFollowUp,
    Integer parentQuestionIndex,
    String referenceAnswer,
    List<String> keyPoints,
    String scoringRubric,
    String sourceContext
) {
    public static InterviewQuestionDTO create(int index, String question, String type, String category) {
        return new InterviewQuestionDTO(
            index, question, type, category, null, null, null, null, false, null, null, null, null, null);
    }

    public static InterviewQuestionDTO create(int index, String question, String type, String category,
                                               String topicSummary, boolean isFollowUp, Integer parentQuestionIndex) {
        return new InterviewQuestionDTO(
            index, question, type, category, topicSummary, null, null, null, isFollowUp, parentQuestionIndex,
            null, null, null, null);
    }

    public static InterviewQuestionDTO fromQuestionBank(int index, String question, String type,
                                                        String category, String topicSummary,
                                                        String referenceAnswer, List<String> keyPoints,
                                                        String scoringRubric, String sourceContext) {
        return new InterviewQuestionDTO(
            index, question, type, category, topicSummary, null, null, null, false, null,
            referenceAnswer, keyPoints, scoringRubric, sourceContext);
    }

    public InterviewQuestionDTO withAnswer(String answer) {
        return new InterviewQuestionDTO(
            questionIndex, question, type, category, topicSummary, answer, score, feedback,
            isFollowUp, parentQuestionIndex, referenceAnswer, keyPoints, scoringRubric, sourceContext);
    }

    public InterviewQuestionDTO withEvaluation(int score, String feedback) {
        return new InterviewQuestionDTO(
            questionIndex, question, type, category, topicSummary, userAnswer, score, feedback,
            isFollowUp, parentQuestionIndex, referenceAnswer, keyPoints, scoringRubric, sourceContext);
    }
}
