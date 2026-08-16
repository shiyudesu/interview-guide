package interview.guide.modules.knowledgebase.listener;

import interview.guide.common.async.AbstractStreamConsumer;
import interview.guide.common.constant.AsyncTaskStreamConstants;
import interview.guide.infrastructure.redis.RedisService;
import interview.guide.modules.knowledgebase.model.QuestionGenerationConfig;
import interview.guide.modules.knowledgebase.service.KnowledgeBaseQuestionGenerationService;
import interview.guide.modules.knowledgebase.service.QuestionGenerationStateService;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.stream.StreamMessageId;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 知识库题目生成 Stream 消费者。
 */
@Slf4j
@Component
public class QuestionGenStreamConsumer
    extends AbstractStreamConsumer<QuestionGenStreamConsumer.QuestionGenPayload> {

  private final KnowledgeBaseQuestionGenerationService generationService;
  private final QuestionGenerationStateService stateService;
  private final QuestionGenStreamProducer producer;

  public record QuestionGenPayload(Long kbId, String taskId) {
  }

  public QuestionGenStreamConsumer(
      RedisService redisService,
      KnowledgeBaseQuestionGenerationService generationService,
      QuestionGenerationStateService stateService,
      QuestionGenStreamProducer producer
  ) {
    super(redisService);
    this.generationService = generationService;
    this.stateService = stateService;
    this.producer = producer;
  }

  @Override
  protected String taskDisplayName() {
    return "题目生成";
  }

  @Override
  protected String streamKey() {
    return AsyncTaskStreamConstants.KB_QUESTION_GEN_STREAM_KEY;
  }

  @Override
  protected String groupName() {
    return AsyncTaskStreamConstants.KB_QUESTION_GEN_GROUP_NAME;
  }

  @Override
  protected String consumerPrefix() {
    return AsyncTaskStreamConstants.KB_QUESTION_GEN_CONSUMER_PREFIX;
  }

  @Override
  protected String threadName() {
    return "question-gen-consumer";
  }

  @Override
  protected QuestionGenPayload parsePayload(
      StreamMessageId messageId,
      Map<String, String> data
  ) {
    String kbId = data.get(AsyncTaskStreamConstants.FIELD_KB_ID);
    String taskId = data.get(AsyncTaskStreamConstants.FIELD_TASK_ID);
    if (kbId == null || taskId == null) {
      log.warn("题目生成消息格式错误，丢弃: messageId={}", messageId);
      return null;
    }
    return new QuestionGenPayload(Long.parseLong(kbId), taskId);
  }

  @Override
  protected String payloadIdentifier(QuestionGenPayload payload) {
    return "kbId=" + payload.kbId() + ", taskId=" + payload.taskId();
  }

  @Override
  protected void markProcessing(QuestionGenPayload payload) {
    // 题目生成使用 tryMarkProcessing 原子领取。
  }

  @Override
  protected boolean tryMarkProcessing(QuestionGenPayload payload) {
    return stateService.tryMarkProcessing(payload.kbId(), payload.taskId());
  }

  @Override
  protected void processBusiness(QuestionGenPayload payload) {
    QuestionGenerationConfig config = stateService.getConfig(payload.kbId(), payload.taskId());
    generationService.executeGeneration(payload.kbId(), payload.taskId(), config);
  }

  @Override
  protected void markCompleted(QuestionGenPayload payload) {
    // 题目替换和 COMPLETED 状态已在同一事务中提交。
  }

  @Override
  protected void markFailed(QuestionGenPayload payload, String error) {
    stateService.markFailed(payload.kbId(), payload.taskId());
  }

  @Override
  protected void retryMessage(QuestionGenPayload payload, int retryCount) {
    if (!stateService.resetForRetry(payload.kbId(), payload.taskId())) {
      log.info("题目生成任务已失效，不再重试: kbId={}, taskId={}",
          payload.kbId(), payload.taskId());
      return;
    }
    producer.sendGenerateTask(payload.kbId(), payload.taskId(), retryCount);
  }
}
