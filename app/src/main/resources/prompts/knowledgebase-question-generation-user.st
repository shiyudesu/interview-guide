# Task
请为知识库《{knowledgeBaseName}》生成 {questionCount} 道面试题草稿。

difficulty: {difficulty}

# Existing Categories
{existingCategories}

# Existing Questions
以下题目已经出过，请从不同知识点或不同考察角度出题，避免题面或考察点重复：
{existingQuestions}

# Knowledge Base Context
{context}

# Output Requirements
- category: 面试方向，遵循 system prompt 中的方向归类规则（最多 {categoryLimit} 个不同方向，优先复用已有）
- question: 主问题题干
- type: 可选的技术分类 key，例如 JVM、REDIS、SPRING；不需要时可留空
- topicSummary: 不超过 80 字的知识点摘要
- referenceAnswer: 参考答案
- keyPoints: 评分要点列表
- scoringRubric: 10 分制评分规则
- followUps: 每道主问题配 {followUpCount} 个追问，每个追问包含 question、referenceAnswer、keyPoints、scoringRubric；若 {followUpCount} 为 0 则返回空数组
