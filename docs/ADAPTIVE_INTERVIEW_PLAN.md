# 统一自适应面试轮次实施计划

## 1. 问题与目标

当前普通文字面试和知识库专项面试在创建会话时一次性生成主问题与追问，提交答案时只按
`questionIndex + 1` 取下一题。追问无法看到用户刚刚提交的回答，因此只是预设题目。

语音面试使用另一套实时对话链路：每轮把当前回答和历史消息交给流式 LLM，由模型自由决定
追问或换题。三种渠道没有共用轮次决策服务，只有最终评估服务共用。

本次改造目标：

- 只预生成主问题，追问必须基于真实回答动态生成。
- 文字、知识库和语音面试共用同一个轮次决策引擎。
- 使用标准化问题与轮次表，不保留 `questionsJson`、`questionIndex` 等旧协议兼容层。
- 现有 `followUpCount` 改为每道主问题允许的动态追问上限。
- 语音面试使用一次结构化模型调用同时产出决策、过渡语和下一问，再执行 TTS。
- 当前处于开发阶段，清空已有面试会话、答案、评估和语音会话数据，不编写旧数据转换层。

## 2. 已确认决策

| 项目 | 决策 |
| --- | --- |
| 覆盖范围 | 普通文字、知识库专项、语音面试全部统一，分阶段接入 |
| 数据结构 | 新建标准化问题/轮次模型，不保留旧 questionsJson/questionIndex 协议 |
| 历史数据 | 清空现有面试相关开发数据 |
| 语音策略 | 一次结构化调用返回 action、过渡语和下一问，再做 TTS |
| 追问数量 | `followUpCount` 是每道主问题的动态追问上限 |
| 主问题 | 创建会话时预生成，追问不预生成 |
| 上线方式 | 分渠道接入，最终删除临时开关和旧实现 |

## 3. 当前实现

### 3.1 普通文字面试

- `InterviewQuestionService` 的 LangGraph 在创建会话时生成完整 `questions[]`。
- `InterviewQuestion` 已有 `isFollowUp` 和 `parentQuestionIndex`，但追问内容在回答前已确定。
- `InterviewSession.questions_json` 保存完整问题数组。
- Redis `interview:session:*` 缓存同一份 JSON 和 `currentIndex`。
- `POST /api/interview/sessions/{sessionId}/answers` 保存答案后直接返回数组中的下一题。
- 最后一题完成后写入 `interview:evaluate:stream`，Worker 异步生成报告。

### 3.2 知识库专项面试

- 题库生成阶段同时生成主问题和候选追问。
- 创建面试时按方向、难度和追问数量筛选题目，直接把候选追问加入问题数组。
- 会话创建后进入普通文字面试链路。

### 3.3 语音面试

- ASR final 文本进入 `UnifiedVoiceLlmStreamer`。
- 每轮加载历史消息、对话摘要、简历和 Skill。
- 流式 LLM 自由生成回复，Prompt 要求回答模糊时追问。
- 回复按句执行 TTS，WebSocket 返回字幕和音频。
- 语音消息结束后进入 `voice:evaluate:stream`。

## 4. 目标架构

```text
主问题计划
    +
当前问题、当前回答、历史轮次
    +
Skill / 简历 / JD / 知识库参考资料
    +
追问上限、剩余主问题、剩余时间
    ↓
InterviewTurnService
    ↓
FOLLOW_UP / NEXT_MAIN / COMPLETE
    ↓
持久化 Question + Turn + Decision
    ↓
Text JSON / Voice WebSocket + TTS
```

渠道只负责输入输出：

- 文字渠道：REST 提交答案并返回下一题。
- 知识库渠道：提供题目来源、参考答案、关键点和候选追问素材。
- 语音渠道：ASR 提供回答，WebSocket/TTS 输出统一决策结果。

轮次选择、幂等、追问规则、上下文组装和失败回退只能实现一次。

## 5. 数据模型

### 5.1 `interview_sessions`

保留会话级配置和报告字段，调整为：

- `id`
- `session_id`
- `channel`: `TEXT` / `KNOWLEDGE_BASE` / `VOICE`
- `skill_id`
- `difficulty`
- `resume_id`
- `knowledge_base_id`
- `interview_category`
- `llm_provider`
- `planned_main_question_count`
- `max_follow_ups_per_main`
- `current_question_id`
- `status`
- `evaluate_status`
- `evaluate_error`
- `created_at`
- `completed_at`
- 现有报告汇总字段

删除：

- `questions_json`
- `current_question_index`
- 旧 `total_questions` 语义
- `request_id` 以外仅用于旧问题数组推进的字段

新增 `actual_question_count`，表示已经创建的主问题与动态追问总数。

### 5.2 `interview_questions`

每个实际问题一行：

- `id`: UUID，对外作为 `questionId`
- `session_id`: FK
- `kind`: `MAIN` / `FOLLOW_UP`
- `main_order`: 主问题顺序
- `follow_up_order`: 同一主问题下的追问顺序，主问题为 0
- `parent_question_id`: 追问指向主问题
- `question`
- `type`
- `category`
- `topic_summary`
- `reference_answer`
- `key_points_json`
- `scoring_rubric`
- `source_context`
- `decision_reason`
- `created_at`

排序使用 `(main_order, follow_up_order)`，动态插入追问时不需要重排后续主问题。

约束：

- `(session_id, main_order, follow_up_order)` 唯一。
- `FOLLOW_UP` 必须有 `parent_question_id`。
- `MAIN` 的 `follow_up_order = 0`。

### 5.3 `interview_turns`

每次回答和轮次决策一行：

- `id`: UUID，对外作为 `turnId`
- `session_id`: FK
- `question_id`: FK
- `request_id`
- `answer`
- `answer_hash`
- `action`: `FOLLOW_UP` / `NEXT_MAIN` / `COMPLETE`
- `acknowledgement`
- `next_question_id`
- `decision_reason`
- `decision_status`: `PROCESSING` / `COMPLETED` / `FALLBACK` / `FAILED`
- `provider_id`
- `error`
- `answered_at`
- `decided_at`

唯一索引：

- `(session_id, request_id)`
- `(session_id, question_id, answer_hash)`

重复请求返回已经保存的决策，不再次调用模型或创建追问。

### 5.4 语音扩展

保留语音专用运行数据，但改成核心会话的扩展表：

- `voice_interview_sessions.interview_session_id` 唯一 FK。
- 保留 phase、planned_duration、actual_duration、暂停时间等语音字段。
- `voice_interview_messages` 保留原始字幕和 AI 文本，用于审计和上下文压缩。
- 问题、回答和评估的权威数据改为 `interview_questions` 与 `interview_turns`。

## 6. Alembic 与数据清理

新增一个显式破坏性 Alembic 版本：

1. 清空以下开发数据：
   - `interview_answers`
   - `interview_sessions`
   - `voice_interview_messages`
   - `voice_interview_evaluations`
   - `voice_interview_sessions`
2. 删除旧 `interview_answers` 表。
3. 重建 `interview_sessions` 的问题推进字段。
4. 创建 `interview_questions` 和 `interview_turns`。
5. 重建必要约束、外键和索引。
6. 保留简历、知识库、知识库题库、Provider 和日程数据。

Redis 不做全库清理：

- 面试会话 key 切换到版本化前缀，例如 `interview:v2:session:*`。
- 清理旧文字/语音会话缓存、创建锁和结果缓存。
- 清理 `interview:evaluate:stream`、`voice:evaluate:stream` 中无法关联新会话的开发消息。
- Worker 重启后重新创建 consumer group。

## 7. 统一轮次决策模型

### 7.1 输入 `InterviewTurnContext`

- 会话渠道和配置
- 当前问题
- 当前答案
- 当前主问题下已发生的追问
- 最近若干轮问答
- Skill persona 和 reference
- 简历文本或 JD
- 知识库 reference answer、key points、rubric、source context
- 候选追问素材
- 剩余主问题数
- `maxFollowUpsPerMain`
- 语音剩余时间

### 7.2 输出 `TurnDecision`

```json
{
  "action": "FOLLOW_UP",
  "acknowledgement": "你提到了缓存穿透，但治理方案还不够具体。",
  "question": "如果攻击者持续请求不存在的 key，你会如何组合布隆过滤器和空值缓存？",
  "reasonCode": "MISSING_IMPLEMENTATION_DETAIL",
  "reason": "回答只有概念，没有说明落地方案",
  "targetTopic": "缓存穿透",
  "confidence": 0.91
}
```

约束：

- `FOLLOW_UP` 必须返回一个新问题。
- `NEXT_MAIN` 使用已规划的下一道主问题，模型不能擅自替换。
- `COMPLETE` 只在没有剩余主问题、用户结束或时间预算耗尽时允许。
- acknowledgement 和 question 都限制长度，适配文字和语音。
- 不输出 Markdown、长解释或评分结果。

### 7.3 追问规则

允许追问：

- 回答过短或含糊。
- 关键概念错误。
- 只给结论，没有实现、取舍或故障处理。
- 回答中出现值得深入的项目细节。
- 知识库关键点缺失。

禁止追问：

- 达到 `maxFollowUpsPerMain`。
- 已经追问过相同主题。
- 用户明确要求跳过或换题。
- 没有剩余时间。
- 当前问题或答案为空且应该直接跳过。
- 模型置信度低于阈值。

## 8. `InterviewTurnService`

处理一次回答：

1. 校验会话状态、当前 `questionId` 和 `requestId`。
2. 查询已有 Turn，命中则直接返回。
3. 保存答案并创建 `PROCESSING` Turn。
4. 构建 `InterviewTurnContext`。
5. 调用一次结构化模型。
6. 校验 action、追问上限、重复主题和剩余时间。
7. 在事务中：
   - `FOLLOW_UP`：创建下一条追问。
   - `NEXT_MAIN`：选择下一个主问题。
   - `COMPLETE`：结束会话并触发评估。
8. 更新 `current_question_id` 和 `actual_question_count`。
9. 保存 Turn 决策。
10. 发布必要的评估 Stream 消息。

失败回退：

- 模型超时、解析失败或 Provider 不可用时，不阻塞面试。
- 有剩余主问题则保存 `FALLBACK + NEXT_MAIN`。
- 没有剩余主问题则保存 `FALLBACK + COMPLETE`。
- 回退原因只记录在日志和 Turn error，不向用户暴露内部异常。

## 9. 普通文字面试改造

### 9.1 会话创建

- `InterviewQuestionService` 只生成主问题。
- Prompt 和结构化 Schema 删除静态追问字段。
- 主问题写入 `interview_questions`。
- API 返回会话配置、当前问题和已完成 Turns，不返回整个预生成问题数组。

### 9.2 API

新接口：

```text
POST /api/interview/sessions
GET  /api/interview/sessions/{sessionId}
GET  /api/interview/sessions/{sessionId}/current-question
POST /api/interview/sessions/{sessionId}/turns
POST /api/interview/sessions/{sessionId}/complete
```

提交 Turn：

```json
{
  "requestId": "answer-uuid",
  "questionId": "question-uuid",
  "answer": "..."
}
```

响应：

```json
{
  "turnId": "turn-uuid",
  "action": "FOLLOW_UP",
  "acknowledgement": "...",
  "nextQuestion": {
    "questionId": "question-uuid",
    "kind": "FOLLOW_UP",
    "parentQuestionId": "main-question-uuid",
    "question": "..."
  },
  "completed": false,
  "progress": {
    "completedMainQuestions": 2,
    "plannedMainQuestions": 5,
    "followUpsUsedForCurrentMain": 1,
    "maxFollowUpsPerMain": 2
  }
}
```

删除旧 `/answers`、`questionIndex`、`currentQuestionIndex` 和 `questions[]` API。

## 10. 知识库专项面试改造

- 题库继续保存候选追问、参考答案、关键点和 rubric。
- 创建会话时只抽取主问题。
- `followUpCount` 不再要求题库必须提前拥有等量追问，而是动态追问上限。
- 候选追问作为 TurnContext 素材，不能原样无条件返回。
- 模型根据实际回答选择、改写或新建追问。
- 动态追问必须继承主问题的知识库来源和 parentQuestionId。
- 容量接口改为只计算满足方向和难度的主问题数量，同时返回可用参考资料覆盖情况。

## 11. 语音面试改造

- ASR partial 继续只用于字幕。
- ASR final 形成一次 Turn 提交。
- 删除 `UnifiedVoiceLlmStreamer` 的自由对话决策职责。
- 调用共享 `InterviewTurnService`，一次结构化模型调用返回 action、acknowledgement 和 question。
- WebSocket 先发送 `turn_deciding` 控制消息。
- 决策完成后发送：
  - acknowledgement 字幕
  - question 字幕
  - TTS `audio_chunk`
  - `audio_complete`
- TTS 仍按完整句子并发合成，但不再额外调用模型润色。
- 暂停、恢复、断线重连、上下文摘要和阶段计时继续由语音扩展层负责。
- 语音消息与标准 Turn 同时保存，标准 Turn 是评估权威数据。

## 12. 评估与报告

`UnifiedEvaluationService` 改为读取标准化问题和 Turns：

- 主问题和追问按 parentQuestionId 分组。
- 主问题评估基础理解。
- 追问评估技术深度、补充能力和修正能力。
- 同一主问题组生成一个综合得分，避免追问作为独立题重复加权。
- 报告问题详情返回树形结构：

```text
Main Question
├── Main Answer
├── Follow-up Question
└── Follow-up Answer
```

- 文字、知识库和语音报告共用同一 DTO 和前端组件。
- `GET /report` 只读取已保存报告。
- 显式重新生成使用单独 POST 接口，并执行幂等和状态检查。

## 13. 前端改造

- 类型从 `questionIndex` 改为 `questionId` / `turnId`。
- 创建会话后只保存当前问题和 Turns。
- 提交答案时生成唯一 `requestId`。
- 等待决策时显示“正在分析回答”。
- 区分：
  - 主问题
  - 针对性追问
  - 进入下一题
- 进度显示主问题进度，不把动态追问加入分母。
- 重试提交必须复用原 requestId。
- 恢复会话时按 Turns 重建消息历史。
- 知识库配置文案改为“每道主问题最多追问 N 次”。
- 语音页面显示 `turn_deciding`、连接状态和决策失败回退。
- 报告页面按主问题分组展示追问链。

## 14. 可观测性

增加指标：

- `interview_turn_decision_duration_seconds`
- `interview_turn_decisions_total{channel,action}`
- `interview_turn_fallback_total{channel,reason}`
- `interview_follow_ups_total{channel}`
- `interview_turn_duplicate_requests_total`
- 决策模型 Token 和费用

日志字段：

- sessionId
- questionId
- turnId
- channel
- action
- reasonCode
- providerId
- durationMs
- fallback

不记录完整用户回答、简历或知识库内容。

## 15. 实施顺序

1. 新增 Alembic 破坏性数据重置和标准化表。
2. 实现 Question、Turn、Decision Repository 和 Pydantic Model。
3. 实现共享 Context Builder、Decision Prompt 和 `InterviewTurnService`。
4. 修改主问题生成，删除静态追问。
5. 接入普通文字面试 API 和前端。
6. 接入知识库专项面试。
7. 接入语音 ASR/WebSocket/TTS。
8. 改造统一评估和报告。
9. 增加指标、日志和失败恢复。
10. 删除旧问题数组、旧接口、旧缓存 key 和临时渠道开关。
11. 更新 README、CONFIGURATION、OPERATIONS、AGENTS 和仓库清单。

## 16. 测试

### 单元测试

- 完整回答返回 `NEXT_MAIN`。
- 模糊回答返回针对性 `FOLLOW_UP`。
- 错误回答追问关键错误点。
- 达到追问上限后不能继续追问。
- 用户跳过后直接下一主问题。
- 无剩余主问题返回 `COMPLETE`。
- 重复 requestId 返回同一 Turn。
- 相同 questionId + answerHash 不重复调用模型。
- 模型超时和非法 JSON 正确 fallback。
- 知识库候选追问只作为素材。
- 主问题组综合评分不重复加权。

### 集成测试

- 真实 PostgreSQL 外键、唯一索引和事务。
- Redis 重复请求锁、缓存恢复和 Stream ACK。
- 文字会话创建、动态追问、结束和报告。
- 知识库主问题抽取和动态追问。
- 语音 ASR final 到 Turn、TTS 和评估。
- Worker Pending reclaim 和失败状态。
- Scheduler 恢复未完成 Turn 和语音会话。

### 前端与 Playwright

- 主问题后出现动态追问。
- 无追问时直接下一题。
- 提交中刷新后恢复同一 Turn。
- 网络重试不创建重复追问。
- 知识库追问上限文案和进度。
- 语音 `turn_deciding` 到字幕/TTS。
- 报告按主问题树展示。

### 真实模型验收

受保护 Key 运行：

- 明显缺少实现细节的回答必须产生追问。
- 完整回答必须进入下一主问题。
- 追问必须引用当前回答中的具体内容。
- 文字、知识库和语音使用同一决策 Schema。
- 记录真实调用次数、Token、费用和决策延迟。
- 不能用 fake 代替真实验收。

## 17. 完成标准

- 创建会话时不存在预生成追问。
- 三种渠道只调用一个 `InterviewTurnService`。
- API 和前端不再使用 questionIndex、currentQuestionIndex 和 questionsJson。
- 数据库没有旧 interview_answers 和问题数组推进字段。
- `followUpCount` 在所有渠道中都是动态追问上限。
- 重复提交不会重复调用模型或创建追问。
- 模型失败不会让面试卡住。
- 语音只进行一次决策模型调用，不增加二次润色费用。
- 报告正确表达主问题和追问关系。
- Ruff、mypy、pytest、前端测试、Playwright、生产 Compose 和真实模型工作流通过。
- 临时开关、旧缓存 key、旧 API、旧 DTO 和旧测试全部删除。

## 18. 风险与控制

- 动态决策增加文字面试每轮延迟：限制 Prompt、输出 Token 和超时，前端显示决策状态。
- 模型可能过度追问：服务端强制上限、重复主题检测和置信度阈值。
- 并发重复提交：数据库唯一索引是最终防线，Redis 只用于减少等待。
- 语音失去逐 Token 文本输出：先发送 `turn_deciding`，决策完成后立即并发 TTS。
- 破坏性数据迁移：只删除面试相关开发数据，迁移前打印目标表和行数，CI 使用空 volume 验证。
- 三渠道分阶段期间出现双实现：使用临时渠道开关，最终阶段必须删除旧实现和开关。
