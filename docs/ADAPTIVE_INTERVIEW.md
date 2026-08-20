# 统一自适应面试

## 能力概览

普通文字、知识库专项和语音面试统一使用标准化主问题、动态追问和 Turn 状态机：

- 会话创建时只生成或抽取主问题。
- 回答提交后最多调用一次结构化模型决定追问或进入下一主问题。
- 每次提交回答后，基于当前真实回答即时决定是否生成追问。
- 三种渠道共用 `InterviewTurnService`、幂等规则和统一评估服务。

## 数据结构

`interview_sessions` 保存渠道、计划主问题数、每题追问上限和当前问题 UUID。

`interview_questions` 每个实际问题一行，使用：

- `kind`: `MAIN` / `FOLLOW_UP`
- `main_order` 与 `follow_up_order`
- `parent_question_id`
- 知识库参考答案、关键点、rubric 和 source context 快照

`interview_turns` 每个已提交回答一行，保存 requestId、answer hash、决策、下一问题、
Provider、Token、耗时、租约和错误信息。

唯一约束：

- `(interview_session_id, request_id)`
- `(interview_session_id, question_id)`
- `(interview_session_id, main_order, follow_up_order)`

语音会话通过唯一 `interview_session_id` 关联核心会话，语音消息可关联标准 Turn。

## API

文字提交接口：

```text
POST /api/interview/sessions/{sessionId}/turns
```

```json
{
  "requestId": "answer-uuid",
  "questionId": "question-uuid",
  "answer": "..."
}
```

响应包含 `turnId`、`action`、`acknowledgement`、`nextQuestion`、`completed` 和只按主问题
计算的 `progress`。重复 requestId 且载荷相同返回原结果；载荷不同返回业务错误。

## Turn 状态机

1. 短事务锁定会话、验证当前问题并创建带租约的 `PROCESSING` Turn。
2. 先执行空回答、跳过、追问上限、剩余主问题和语音时间预算规则。
3. 只有仍可能追问时才调用结构化模型；`max_attempts=1`，不调用 Tool，不隐式重试。
4. 低于 0.65 置信度或重复主题时强制进入下一主问题。
5. 第二个短事务创建追问或选择已规划主问题，并更新 Turn 和当前问题。
6. 完成会话时同事务写入 `evaluate_status=PENDING`，提交后写评估 Stream。
7. Scheduler 回收租约过期 Turn，并对遗漏的 PENDING 评估重新入队，不再次调用决策模型。

模型只能输出 `FOLLOW_UP` 或 `NEXT_MAIN`；`COMPLETE` 只能由服务端状态机产生。

上下文只包含当前主问题链、最近六轮、受限简历/JD/Skill 和题目参考资料，所有外部内容
通过 PromptSanitizer 和数据边界包装。普通面试在创建会话时按主问题分类保存 Skill reference
快照，知识库面试保存参考答案、关键点、rubric、来源片段和候选追问素材；后续追问与评估均读取
题目快照，不实时访问外部题库。轮次主链路不再同步调用模型生成语音上下文摘要。

## 渠道行为

### 普通文字

`APP_INTERVIEW_FOLLOW_UP_COUNT` 是每道主问题的动态追问上限。前端在请求发出前生成
requestId，失败重试和页面恢复必须复用。

### 知识库专项

创建会话只抽取满足方向和难度的主问题。题库候选追问用作轮次决策素材；容量按可用主问题
计算，并返回参考答案、关键点和 rubric 覆盖数量。

### 语音

- 计划时长必须为 15–60 分钟且为 5 的倍数。
- 每 5 分钟规划一道主问题，启用阶段至少各一题。
- 剩余额度按 TECH 50%、PROJECT 30%、HR 20% 分配，INTRO 启用时固定至少一题。
- ASR final 只更新字幕，仍由显式 `control/submit` 提交 Turn。
- WebSocket 发送 `turn_deciding`，随后发送最终文本、Base64 音频分块和 `audio_complete`。
- 断线不自动完成会话，客户端可重连；显式暂停和 Scheduler 负责生命周期清理。

## 评估

统一评估按主问题组评分。追问影响技术深度、补充和纠错评价，但不作为独立题重复加权。
总分是已回答主问题组的等权平均，未回答的计划问题不计入平均分。

`GET /report` 只读取保存结果，`POST /report` 幂等触发重新生成。文字和语音评估统一写入
`interview:evaluate:stream`，并保持 Pending、reclaim、重试和 ACK 顺序。

## 运行与恢复

- Alembic 管理当前面试表结构和约束，API 不直接执行 schema 变更。
- Redis 会话缓存使用 `interview:create:*`、`interview:turn:*` 与 `voice:interview:*`。
- Worker 按 Stream 消费评估任务，失败时先重投或写失败状态，再执行 ACK。
- Scheduler 回收租约过期的 Turn、恢复遗漏的评估任务并清理过期语音会话。
- requestId 幂等锁、结果缓存和数据库唯一索引共同防止重复决策与重复写入。
- 文本长度和上下文截断按 Unicode 字符计算；稳定输出使用显式排序，不依赖运行时 hash。

## 质量保障

- 单元测试覆盖轮次决策、幂等提交、追问上限、确定性回退、评估聚合和语音生命周期。
- 集成测试使用真实 PostgreSQL、Redis 和 S3 兼容存储验证迁移、事务与异步任务。
- 前端状态测试和 Playwright 覆盖文字面试、知识库专项面试、语音提交与报告展示。
- 生产 Compose 验证 Migrate、API、Worker、Scheduler、前端代理和 Python-only 镜像。
- 真实模型验收覆盖动态轮次决策、Embedding、ASR、TTS 和异步报告生成。

回归检查命令见根目录
[README](../README.md)，配置见 [CONFIGURATION.md](CONFIGURATION.md)，部署和排障见
[OPERATIONS.md](OPERATIONS.md)。
