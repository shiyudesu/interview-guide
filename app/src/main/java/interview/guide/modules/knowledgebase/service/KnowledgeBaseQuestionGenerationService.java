package interview.guide.modules.knowledgebase.service;

import interview.guide.common.ai.LlmProviderRegistry;
import interview.guide.common.ai.PromptSanitizer;
import interview.guide.common.ai.PromptSecurityConstants;
import interview.guide.common.ai.StructuredOutputInvoker;
import interview.guide.common.constant.CommonConstants.InterviewDefaults;
import interview.guide.common.exception.BusinessException;
import interview.guide.common.exception.ErrorCode;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseEntity;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionEntity;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionFollowUpDTO;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionStatus;
import interview.guide.modules.knowledgebase.model.QuestionGenerationConfig;
import interview.guide.modules.knowledgebase.repository.KnowledgeBaseQuestionRepository;
import interview.guide.modules.knowledgebase.repository.KnowledgeBaseRepository;
import interview.guide.modules.knowledgebase.repository.KnowledgeBaseQuestionRepository.CategoryCount;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.prompt.PromptTemplate;
import org.springframework.ai.converter.BeanOutputConverter;
import org.springframework.ai.document.Document;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 知识库问题异步生成服务
 * 由 QuestionGenStreamConsumer 调用，负责实际的 LLM 生成和结果持久化。
 * LLM 调用不在事务内；删除旧问题和保存新问题在同一个最小事务中完成。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeBaseQuestionGenerationService {

  private static final int RETRIEVAL_TOP_K = 12;
  private static final int RETRIEVAL_QUERY_TOP_K = 4;
  private static final int MAX_CONTEXT_CHARS = 5000;

  private final KnowledgeBaseRepository knowledgeBaseRepository;
  private final KnowledgeBaseQuestionRepository questionRepository;
  private final KnowledgeBaseVectorService vectorService;
  private final LlmProviderRegistry llmProviderRegistry;
  private final StructuredOutputInvoker structuredOutputInvoker;
  private final PromptSanitizer promptSanitizer;
  private final QuestionGenerationStateService stateService;
  private final ObjectMapper objectMapper;

  @Value("classpath:prompts/knowledgebase-question-generation-system.st")
  private Resource systemPromptResource;

  @Value("classpath:prompts/knowledgebase-question-generation-user.st")
  private Resource userPromptResource;

  private final BeanOutputConverter<QuestionListDTO> outputConverter =
      new BeanOutputConverter<>(QuestionListDTO.class);

  record QuestionListDTO(List<QuestionDTO> questions) {}

  record QuestionDTO(
      String category,
      String type,
      String question,
      String topicSummary,
      String referenceAnswer,
      List<String> keyPoints,
      String scoringRubric,
      List<KnowledgeBaseQuestionFollowUpDTO> followUps
  ) {}

  private record GenerationBatch(
      List<KnowledgeBaseQuestionEntity> questions,
      int skippedCount
  ) {
  }

  /**
   * 执行问题生成（由 Consumer 调用，不在事务中）
   * 流程：校验 → 检索上下文 → 调用 LLM → 替换旧问题并保存新问题（小事务）
   */
  public void executeGeneration(
      Long kbId,
      String taskId,
      QuestionGenerationConfig config
  ) {
    KnowledgeBaseEntity kb = knowledgeBaseRepository.findById(kbId)
        .orElseThrow(() -> new BusinessException(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND));

    // 再次确认任务ID匹配
    if (!taskId.equals(kb.getQuestionGenTaskId())) {
      log.info("任务ID不匹配，放弃生成: kbId={}, msgTaskId={}, currentTaskId={}",
          kbId, taskId, kb.getQuestionGenTaskId());
      return;
    }

    String normalizedDifficulty = normalizeDifficulty(config.difficulty());
    int normalizedFollowUp = Math.max(0, Math.min(config.followUpCount(), 5));
    int normalizedCategoryLimit = Math.max(1, Math.min(config.categoryLimit(), 5));

    // 1. 检索上下文（不在事务中）
    String context = buildGenerationContext(kb);

    // 2. 调用 LLM（不在事务中）
    ChatClient chatClient = llmProviderRegistry.getPlainChatClient(config.llmProvider());
    QuestionListDTO generated = callLlm(kb, chatClient, normalizedDifficulty,
        Math.max(1, config.questionCount()), normalizedFollowUp, normalizedCategoryLimit, context);

    // 3. 校验生成结果
    if (generated == null || generated.questions() == null || generated.questions().isEmpty()) {
      throw new BusinessException(ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED, "知识库题库生成结果为空");
    }

    // 4. 构建实体列表（不在事务中）
    GenerationBatch batch =
        buildEntities(kb, normalizedDifficulty, context, normalizedFollowUp, generated);
    if (batch.questions().isEmpty()) {
      throw new BusinessException(ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED, "知识库题库生成结果无有效题干");
    }

    // 5. 在一个小事务中校验当前任务、替换题目并更新完成状态
    boolean completed = stateService.replaceQuestionsAndComplete(
        kbId, taskId, batch.questions(), batch.skippedCount());
    if (!completed) {
      log.info("题目生成任务已被替换，丢弃旧结果: kbId={}, taskId={}", kbId, taskId);
      return;
    }

    log.info("知识库问题异步生成完成: kbId={}, taskId={}, count={}",
        kbId, taskId, batch.questions().size());
  }

  private QuestionListDTO callLlm(
      KnowledgeBaseEntity kb,
      ChatClient chatClient,
      String difficulty,
      int questionCount,
      int followUpCount,
      int categoryLimit,
      String context
  ) {
    try {
      String systemPrompt = loadTemplate(systemPromptResource).render()
          + "\n\n"
          + outputConverter.getFormat();
      String userPrompt = loadTemplate(userPromptResource)
          .render(Map.of(
              "knowledgeBaseName", promptSanitizer.sanitize(kb.getName()),
              "difficulty", difficulty,
              "questionCount", questionCount,
              "followUpCount", followUpCount,
              "categoryLimit", categoryLimit,
              "existingCategories", promptSanitizer.sanitize(
                  buildExistingCategorySection(kb.getId())),
              "existingQuestions", promptSanitizer.sanitize(
                  buildExistingQuestionSection(kb.getId(), difficulty)),
              "context", PromptSecurityConstants.DATA_BOUNDARY_INSTRUCTION + "\n"
                  + promptSanitizer.wrapWithDelimiters("knowledge-base",
                      promptSanitizer.sanitize(context))
          ));

      return structuredOutputInvoker.invoke(
          chatClient,
          systemPrompt,
          userPrompt,
          outputConverter,
          ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
          "知识库题库生成失败：",
          "知识库题库生成",
          log
      );
    } catch (BusinessException e) {
      throw e;
    } catch (Exception e) {
      log.error("知识库题库生成LLM调用失败: kbId={}, error={}", kb.getId(), e.getMessage(), e);
      throw new BusinessException(ErrorCode.INTERVIEW_QUESTION_GENERATION_FAILED,
          "知识库题库生成失败：" + e.getMessage());
    }
  }

  private GenerationBatch buildEntities(
      KnowledgeBaseEntity kb,
      String difficulty,
      String sourceContext,
      int followUpCount,
      QuestionListDTO generated
  ) {
    List<KnowledgeBaseQuestionEntity> entities = new ArrayList<>();
    Set<String> batchKeys = new LinkedHashSet<>();
    int skippedCount = 0;
    for (QuestionDTO dto : generated.questions()) {
      if (dto == null || dto.question() == null || dto.question().isBlank()) {
        skippedCount += 1;
        continue;
      }
      String rawQuestion = dto.question().trim();
      String key = normalizeQuestionKey(rawQuestion);
      if (!batchKeys.add(key)) {
        skippedCount += 1;
        continue;
      }
      String category = normalizeCategory(dto.category(), kb.getName());
      KnowledgeBaseQuestionEntity entity = new KnowledgeBaseQuestionEntity();
      entity.setKnowledgeBase(kb);
      entity.setSkillId(KnowledgeBaseQuestionEntity.DEFAULT_SKILL_ID);
      entity.setDifficulty(difficulty);
      entity.setType(trimToNull(dto.type()));
      entity.setCategory(category);
      entity.setQuestion(rawQuestion);
      entity.setTopicSummary(trimToNull(dto.topicSummary()));
      entity.setReferenceAnswer(trimToNull(dto.referenceAnswer()));
      entity.setKeyPointsJson(writeStringList(dto.keyPoints()));
      entity.setScoringRubric(trimToNull(dto.scoringRubric()));
      entity.setFollowUpsJson(writeFollowUps(dto.followUps(), followUpCount));
      entity.setSourceContext(sourceContext);
      entity.setKbContentHash(kb.getFileHash());
      entity.setStatus(KnowledgeBaseQuestionStatus.DRAFT);
      entities.add(entity);
    }
    return new GenerationBatch(entities, skippedCount);
  }

  private String buildGenerationContext(KnowledgeBaseEntity kb) {
    List<Document> docs = new ArrayList<>();
    Set<String> seenTexts = new LinkedHashSet<>();
    for (String query : buildGenerationQueries()) {
      List<Document> hits = vectorService.similaritySearch(
          query, List.of(kb.getId()), RETRIEVAL_QUERY_TOP_K, 0);
      for (Document doc : hits) {
        String text = doc.getText();
        if (text == null || text.isBlank() || !seenTexts.add(text.trim())) {
          continue;
        }
        docs.add(doc);
        if (docs.size() >= RETRIEVAL_TOP_K) {
          break;
        }
      }
      if (docs.size() >= RETRIEVAL_TOP_K) {
        break;
      }
    }
    if (docs.isEmpty()) {
      throw new BusinessException(ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
          "知识库未检索到可用于生成题目的内容");
    }
    String context = docs.stream()
        .map(Document::getText)
        .collect(Collectors.joining("\n\n---\n\n"));
    return context.length() <= MAX_CONTEXT_CHARS
        ? context
        : context.substring(0, MAX_CONTEXT_CHARS) + "\n...(知识库片段过长，已截断)";
  }

  private List<String> buildGenerationQueries() {
    return List.of(
        "核心概念 定义 背景 原理",
        "关键流程 步骤 方法 工作机制",
        "规则约束 条件 边界 例外 限制",
        "典型案例 常见问题 应用场景 最佳实践"
    );
  }

  private String buildExistingCategorySection(Long knowledgeBaseId) {
    List<CategoryCount> categories = questionRepository.findCategoryCounts(knowledgeBaseId);
    if (categories.isEmpty()) {
      return "暂无已有方向";
    }
    return categories.stream()
        .limit(10)
        .map(c -> "- " + c.getCategory() + "（" + c.getCount() + " 题）")
        .collect(Collectors.joining("\n"));
  }

  private String buildExistingQuestionSection(Long knowledgeBaseId, String difficulty) {
    List<String> questions = questionRepository
        .findTop20ByKnowledgeBase_IdAndDifficultyOrderByUpdatedAtDesc(knowledgeBaseId, difficulty)
        .stream()
        .map(KnowledgeBaseQuestionEntity::getQuestion)
        .filter(question -> question != null && !question.isBlank())
        .map(question -> "- " + question.trim())
        .toList();
    return questions.isEmpty() ? "暂无已有题目" : String.join("\n", questions);
  }

  private PromptTemplate loadTemplate(Resource resource) throws IOException {
    try (var input = resource.getInputStream()) {
      String content = new String(input.readAllBytes(), StandardCharsets.UTF_8);
      return new PromptTemplate(content);
    }
  }

  private String normalizeDifficulty(String difficulty) {
    if (difficulty == null || difficulty.isBlank()) {
      return InterviewDefaults.DIFFICULTY;
    }
    return difficulty.trim();
  }

  private String normalizeCategory(String category, String fallback) {
    if (category == null || category.isBlank()) {
      return fallback != null && !fallback.isBlank() ? fallback.trim() : "未分类";
    }
    return category.trim();
  }

  private String trimToNull(String value) {
    if (value == null || value.isBlank()) {
      return null;
    }
    return value.trim();
  }

  private String normalizeQuestionKey(String question) {
    if (question == null) {
      return "";
    }
    String normalized = Normalizer.normalize(question, Normalizer.Form.NFC).toLowerCase(Locale.ROOT);
    StringBuilder sb = new StringBuilder(normalized.length());
    for (int i = 0; i < normalized.length(); i += 1) {
      char ch = normalized.charAt(i);
      if (Character.isLetterOrDigit(ch)) {
        sb.append(ch);
      }
    }
    return sb.toString();
  }

  private String writeStringList(List<String> values) {
    try {
      List<String> sanitized = values == null ? List.of() : values.stream()
          .filter(value -> value != null && !value.isBlank())
          .map(String::trim)
          .toList();
      return objectMapper.writeValueAsString(sanitized);
    } catch (JacksonException e) {
      throw new BusinessException(ErrorCode.INTERNAL_ERROR, "序列化题目列表字段失败", e);
    }
  }

  private String writeFollowUps(
      List<KnowledgeBaseQuestionFollowUpDTO> values,
      int followUpCount
  ) {
    try {
      List<KnowledgeBaseQuestionFollowUpDTO> sanitized = values == null ? List.of() : values.stream()
          .filter(value -> value != null && value.question() != null && !value.question().isBlank())
          .map(value -> new KnowledgeBaseQuestionFollowUpDTO(
              value.question().trim(),
              trimToNull(value.referenceAnswer()),
              value.keyPoints() == null ? List.of() : value.keyPoints().stream()
                  .filter(item -> item != null && !item.isBlank())
                  .map(String::trim)
                  .toList(),
              trimToNull(value.scoringRubric())
          ))
          .limit(followUpCount)
          .toList();
      return objectMapper.writeValueAsString(sanitized);
    } catch (JacksonException e) {
      throw new BusinessException(ErrorCode.INTERNAL_ERROR, "序列化追问字段失败", e);
    }
  }
}
