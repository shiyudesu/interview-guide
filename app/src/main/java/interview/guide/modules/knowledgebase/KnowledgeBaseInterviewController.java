package interview.guide.modules.knowledgebase;

import interview.guide.common.annotation.RateLimit;
import interview.guide.common.result.Result;
import interview.guide.modules.interview.model.InterviewSessionDTO;
import interview.guide.modules.knowledgebase.model.CreateKnowledgeBaseInterviewRequest;
import interview.guide.modules.knowledgebase.model.CreateKnowledgeBaseQuestionRequest;
import interview.guide.modules.knowledgebase.model.GenerateKnowledgeBaseQuestionsRequest;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseInterviewCapacityResponse;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionDTO;
import interview.guide.modules.knowledgebase.model.KnowledgeBaseQuestionStatus;
import interview.guide.modules.knowledgebase.model.QuestionGenStatusResponse;
import interview.guide.modules.knowledgebase.model.UpdateKnowledgeBaseQuestionRequest;
import interview.guide.modules.knowledgebase.model.UpdateKnowledgeBaseQuestionStatusRequest;
import interview.guide.modules.knowledgebase.repository.KnowledgeBaseQuestionRepository.CategoryCount;
import interview.guide.modules.knowledgebase.service.KnowledgeBaseInterviewService;
import interview.guide.modules.knowledgebase.service.KnowledgeBaseQuestionService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;

import java.util.List;

@RestController
@Validated
@RequiredArgsConstructor
public class KnowledgeBaseInterviewController {

  private final KnowledgeBaseQuestionService questionService;
  private final KnowledgeBaseInterviewService interviewService;

  @GetMapping("/api/knowledgebase/{id}/questions")
  public Result<List<KnowledgeBaseQuestionDTO>> listQuestions(
      @PathVariable Long id,
      @RequestParam(value = "status", required = false) KnowledgeBaseQuestionStatus status,
      @RequestParam(value = "category", required = false) String category,
      @RequestParam(value = "difficulty", required = false) String difficulty,
      @RequestParam(value = "keyword", required = false) String keyword) {
    return Result.success(questionService.listQuestions(id, status, category, difficulty, keyword));
  }

  @GetMapping("/api/knowledgebase/{id}/questions/categories")
  public Result<List<CategoryCount>> listCategories(@PathVariable Long id) {
    return Result.success(questionService.listCategories(id));
  }

  @PostMapping("/api/knowledgebase/{id}/questions/generate")
  @RateLimit(dimension = RateLimit.Dimension.GLOBAL, count = 2)
  @RateLimit(dimension = RateLimit.Dimension.IP, count = 2)
  public Result<QuestionGenStatusResponse> generateQuestions(
      @PathVariable Long id,
      @Valid @RequestBody GenerateKnowledgeBaseQuestionsRequest request) {
    return Result.success(questionService.submitGenerationTask(id, request));
  }

  @GetMapping("/api/knowledgebase/{id}/questions/generation-status")
  public Result<QuestionGenStatusResponse> getQuestionGenerationStatus(@PathVariable Long id) {
    return Result.success(questionService.getGenerationStatus(id));
  }

  @PostMapping("/api/knowledgebase/{id}/questions")
  public Result<KnowledgeBaseQuestionDTO> createQuestion(
      @PathVariable Long id,
      @Valid @RequestBody CreateKnowledgeBaseQuestionRequest request) {
    return Result.success(questionService.createQuestion(id, request));
  }

  @PutMapping("/api/knowledgebase/questions/{questionId}")
  public Result<KnowledgeBaseQuestionDTO> updateQuestion(
      @PathVariable Long questionId,
      @RequestBody UpdateKnowledgeBaseQuestionRequest request) {
    return Result.success(questionService.updateQuestion(questionId, request));
  }

  @PutMapping("/api/knowledgebase/questions/{questionId}/status")
  public Result<KnowledgeBaseQuestionDTO> updateQuestionStatus(
      @PathVariable Long questionId,
      @Valid @RequestBody UpdateKnowledgeBaseQuestionStatusRequest request) {
    return Result.success(questionService.updateStatus(questionId, request.status()));
  }

  @DeleteMapping("/api/knowledgebase/questions/{questionId}")
  public Result<Void> deleteQuestion(@PathVariable Long questionId) {
    questionService.deleteQuestion(questionId);
    return Result.success(null);
  }

  @PostMapping("/api/knowledgebase-interviews/sessions")
  public Result<InterviewSessionDTO> createInterviewSession(
      @Valid @RequestBody CreateKnowledgeBaseInterviewRequest request) {
    return Result.success(interviewService.createSession(request));
  }

  @GetMapping("/api/knowledgebase/{id}/interview-capacity")
  public Result<KnowledgeBaseInterviewCapacityResponse> getInterviewCapacity(
      @PathVariable Long id,
      @RequestParam(value = "category", required = false) String category,
      @RequestParam(value = "difficulty", defaultValue = "mid") String difficulty,
      @RequestParam(value = "mainQuestionCount", defaultValue = "5")
      @Min(value = 1, message = "主问题数量最少1题")
      @Max(value = 20, message = "主问题数量最多20题")
      int mainQuestionCount) {
    return Result.success(
        interviewService.getCapacity(id, category, difficulty, mainQuestionCount));
  }
}
