package interview.guide.modules.knowledgebase.listener;

import interview.guide.modules.knowledgebase.model.KnowledgeBaseEntity;
import interview.guide.modules.knowledgebase.model.QuestionGenStatus;
import interview.guide.modules.knowledgebase.repository.KnowledgeBaseRepository;
import interview.guide.modules.knowledgebase.service.QuestionGenerationStateService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 恢复未成功投递或执行节点异常退出的题目生成任务。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class QuestionGenerationRecoveryScheduler {

  private static final long QUEUED_STALE_MINUTES = 2;
  private static final long PROCESSING_STALE_MINUTES = 20;

  private final KnowledgeBaseRepository knowledgeBaseRepository;
  private final QuestionGenerationStateService stateService;
  private final QuestionGenStreamProducer producer;

  @Scheduled(fixedDelay = 60_000, initialDelay = 60_000)
  public void recoverStaleTasks() {
    LocalDateTime now = LocalDateTime.now();
    recoverQueued(now.minusMinutes(QUEUED_STALE_MINUTES));
    recoverProcessing(now.minusMinutes(PROCESSING_STALE_MINUTES));
  }

  private void recoverQueued(LocalDateTime threshold) {
    List<KnowledgeBaseEntity> tasks = knowledgeBaseRepository
        .findStaleQuestionGenerationTasks(QuestionGenStatus.QUEUED, threshold);
    for (KnowledgeBaseEntity task : tasks) {
      String taskId = task.getQuestionGenTaskId();
      if (taskId != null
          && stateService.touchQueuedForRecovery(task.getId(), taskId, threshold)) {
        producer.sendGenerateTask(task.getId(), taskId);
        log.info("重新投递等待中的题目生成任务: kbId={}, taskId={}", task.getId(), taskId);
      }
    }
  }

  private void recoverProcessing(LocalDateTime threshold) {
    List<KnowledgeBaseEntity> tasks = knowledgeBaseRepository
        .findStaleQuestionGenerationTasks(QuestionGenStatus.PROCESSING, threshold);
    for (KnowledgeBaseEntity task : tasks) {
      String taskId = task.getQuestionGenTaskId();
      if (taskId != null
          && stateService.resetStaleProcessing(task.getId(), taskId, threshold)) {
        producer.sendGenerateTask(task.getId(), taskId);
        log.warn("恢复卡住的题目生成任务: kbId={}, taskId={}", task.getId(), taskId);
      }
    }
  }
}
