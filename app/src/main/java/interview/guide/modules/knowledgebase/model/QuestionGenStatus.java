package interview.guide.modules.knowledgebase.model;

/**
 * 知识库问题生成状态
 */
public enum QuestionGenStatus {
    NONE,        // 未开始
    QUEUED,      // 等待处理
    PROCESSING,  // 生成中
    COMPLETED,   // 生成成功
    FAILED       // 生成失败
}
