import { request } from './request';
import { streamSse } from './stream';
import type { InterviewSession } from '../types/interview';

// 向量化状态
export type VectorStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
export type QuestionGenStatus = 'NONE' | 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface KnowledgeBaseItem {
  id: number;
  name: string;
  category: string | null;
  originalFilename: string;
  fileSize: number;
  contentType: string;
  uploadedAt: string;
  lastAccessedAt: string;
  accessCount: number;
  questionCount: number;
  vectorStatus: VectorStatus;
  vectorError: string | null;
  chunkCount: number;
  questionGenStatus: QuestionGenStatus;
  questionGenError: string | null;
}

// 统计信息
export interface KnowledgeBaseStats {
  totalCount: number;
  totalQuestionCount: number;
  totalAccessCount: number;
  completedCount: number;
  processingCount: number;
}

export type SortOption = 'time' | 'size' | 'access' | 'question';

export interface UploadKnowledgeBaseResponse {
  knowledgeBase: {
    id: number;
    name: string;
    category: string;
    fileSize: number;
    contentLength: number;
  };
  storage: {
    fileKey: string;
    fileUrl: string;
  };
  duplicate: boolean;
}

export interface QueryRequest {
  knowledgeBaseIds: number[];  // 支持多个知识库
  question: string;
}

export interface QueryResponse {
  answer: string;
  knowledgeBaseId: number;
  knowledgeBaseName: string;
}

export type KnowledgeBaseQuestionStatus = 'DRAFT' | 'ACTIVE' | 'ARCHIVED' | 'STALE';

export interface KnowledgeBaseQuestionFollowUp {
  question: string;
  referenceAnswer?: string | null;
  keyPoints?: string[];
  scoringRubric?: string | null;
}

export interface KnowledgeBaseQuestion {
  id: number;
  knowledgeBaseId: number;
  knowledgeBaseName: string;
  skillId: string;  // 后端兜底字段，固定为 knowledge-base，不再用于业务筛选
  difficulty: string;
  type: string | null;
  category: string;  // 面试方向，由模型生成或用户填写，用于筛选和开始面试
  question: string;
  topicSummary: string | null;
  referenceAnswer: string | null;
  keyPoints: string[];
  scoringRubric: string | null;
  followUps: KnowledgeBaseQuestionFollowUp[];
  sourceContext: string | null;
  status: KnowledgeBaseQuestionStatus;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateKnowledgeBaseQuestionsRequest {
  difficulty?: string;
  questionCount: number;
  followUpCount?: number;
  categoryLimit?: number;
  llmProvider?: string;
}

export interface QuestionGenerationConfig {
  difficulty: string;
  questionCount: number;
  followUpCount: number;
  categoryLimit: number;
  llmProvider: string | null;
}

export interface QuestionGenStatusResponse {
  knowledgeBaseId: number;
  questionGenStatus: QuestionGenStatus;
  questionGenTaskId: string | null;
  questionGenConfig: QuestionGenerationConfig | null;
  savedCount: number;
  skippedCount: number;
  message: string | null;
  error: string | null;
  updatedAt: string | null;
}

export interface SaveKnowledgeBaseQuestionRequest {
  difficulty?: string;
  type?: string | null;
  category: string;
  question: string;
  topicSummary?: string | null;
  referenceAnswer?: string | null;
  keyPoints?: string[];
  scoringRubric?: string | null;
  followUps?: KnowledgeBaseQuestionFollowUp[];
  sourceContext?: string | null;
  status?: KnowledgeBaseQuestionStatus;
}

export interface ListKnowledgeBaseQuestionsParams {
  status?: KnowledgeBaseQuestionStatus | '';
  category?: string;
  difficulty?: string;
  keyword?: string;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface CreateKnowledgeBaseInterviewRequest {
  knowledgeBaseId: number;
  category?: string;  // 不传则覆盖全部方向
  difficulty?: string;
  mainQuestionCount: number;
  followUpCount: number;
  llmProvider?: string;
}

export interface InterviewCategoryCapacity {
  category: string;
  availableQuestionCount: number;
}

export interface InterviewFollowUpCapacity {
  followUpCount: number;
  availableQuestionCount: number;
  selectable: boolean;
}

export interface KnowledgeBaseInterviewCapacityResponse {
  knowledgeBaseId: number;
  category: string | null;
  difficulty: string;
  mainQuestionCount: number;
  categories: InterviewCategoryCapacity[];
  followUpOptions: InterviewFollowUpCapacity[];
}

export interface GetKnowledgeBaseInterviewCapacityParams {
  category?: string;
  difficulty: string;
  mainQuestionCount: number;
}

export const knowledgeBaseApi = {
  /**
   * 上传知识库文件
   */
  async uploadKnowledgeBase(file: File, name?: string, category?: string): Promise<UploadKnowledgeBaseResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (name) {
      formData.append('name', name);
    }
    if (category) {
      formData.append('category', category);
    }
    return request.upload<UploadKnowledgeBaseResponse>('/api/knowledgebase/upload', formData);
  },

  /**
   * 下载知识库文件
   */
  async downloadKnowledgeBase(id: number): Promise<Blob> {
    return request.download(`/api/knowledgebase/${id}/download`);
  },

  /**
   * 获取所有知识库列表
   */
  async getAllKnowledgeBases(sortBy?: SortOption, vectorStatus?: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'): Promise<KnowledgeBaseItem[]> {
    const params = new URLSearchParams();
    if (sortBy) {
      params.append('sortBy', sortBy);
    }
    if (vectorStatus) {
      params.append('vectorStatus', vectorStatus);
    }
    const queryString = params.toString();
    return request.get<KnowledgeBaseItem[]>(`/api/knowledgebase/list${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * 获取知识库详情
   */
  async getKnowledgeBase(id: number): Promise<KnowledgeBaseItem> {
    return request.get<KnowledgeBaseItem>(`/api/knowledgebase/${id}`);
  },

  /**
   * 删除知识库
   */
  async deleteKnowledgeBase(id: number): Promise<void> {
    return request.delete(`/api/knowledgebase/${id}`);
  },

  // ========== 分类管理 ==========

  /**
   * 获取所有分类
   */
  async getAllCategories(): Promise<string[]> {
    return request.get<string[]>('/api/knowledgebase/categories');
  },

  /**
   * 根据分类获取知识库
   */
  async getByCategory(category: string): Promise<KnowledgeBaseItem[]> {
    return request.get<KnowledgeBaseItem[]>(`/api/knowledgebase/category/${encodeURIComponent(category)}`);
  },

  /**
   * 获取未分类的知识库
   */
  async getUncategorized(): Promise<KnowledgeBaseItem[]> {
    return request.get<KnowledgeBaseItem[]>('/api/knowledgebase/uncategorized');
  },

  /**
   * 更新知识库分类
   */
  async updateCategory(id: number, category: string | null): Promise<void> {
    return request.put(`/api/knowledgebase/${id}/category`, { category });
  },

  // ========== 搜索 ==========

  /**
   * 搜索知识库
   */
  async search(keyword: string): Promise<KnowledgeBaseItem[]> {
    return request.get<KnowledgeBaseItem[]>(`/api/knowledgebase/search?keyword=${encodeURIComponent(keyword)}`);
  },

  // ========== 统计 ==========

  /**
   * 获取知识库统计信息
   */
  async getStatistics(): Promise<KnowledgeBaseStats> {
    return request.get<KnowledgeBaseStats>('/api/knowledgebase/stats');
  },

  // ========== 向量化管理 ==========

  /**
   * 重新向量化知识库（手动重试）
   */
  async revectorize(id: number): Promise<void> {
    return request.post(`/api/knowledgebase/${id}/revectorize`);
  },

  // ========== 知识库面试题库 ==========

  async generateQuestions(
    id: number,
    req: GenerateKnowledgeBaseQuestionsRequest
  ): Promise<QuestionGenStatusResponse> {
    return request.post<QuestionGenStatusResponse>(
      `/api/knowledgebase/${id}/questions/generate`,
      req
    );
  },

  async getQuestionGenerationStatus(id: number): Promise<QuestionGenStatusResponse> {
    return request.get<QuestionGenStatusResponse>(
      `/api/knowledgebase/${id}/questions/generation-status`
    );
  },

  async listQuestions(
    id: number,
    params?: ListKnowledgeBaseQuestionsParams
  ): Promise<KnowledgeBaseQuestion[]> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value) {
          searchParams.append(key, value);
        }
      });
    }
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request.get<KnowledgeBaseQuestion[]>(`/api/knowledgebase/${id}/questions${query}`);
  },

  async listCategories(id: number): Promise<CategoryCount[]> {
    return request.get<CategoryCount[]>(`/api/knowledgebase/${id}/questions/categories`);
  },

  async createQuestion(
    id: number,
    req: SaveKnowledgeBaseQuestionRequest
  ): Promise<KnowledgeBaseQuestion> {
    return request.post<KnowledgeBaseQuestion>(`/api/knowledgebase/${id}/questions`, req);
  },

  async updateQuestion(
    id: number,
    req: Partial<SaveKnowledgeBaseQuestionRequest>
  ): Promise<KnowledgeBaseQuestion> {
    return request.put<KnowledgeBaseQuestion>(`/api/knowledgebase/questions/${id}`, req);
  },

  async updateQuestionStatus(
    id: number,
    status: KnowledgeBaseQuestionStatus
  ): Promise<KnowledgeBaseQuestion> {
    return request.put<KnowledgeBaseQuestion>(`/api/knowledgebase/questions/${id}/status`, { status });
  },

  async deleteQuestion(id: number): Promise<void> {
    return request.delete(`/api/knowledgebase/questions/${id}`);
  },

  async createInterviewSession(req: CreateKnowledgeBaseInterviewRequest): Promise<InterviewSession> {
    return request.post<InterviewSession>('/api/knowledgebase-interviews/sessions', req);
  },

  async getInterviewCapacity(
    id: number,
    params: GetKnowledgeBaseInterviewCapacityParams
  ): Promise<KnowledgeBaseInterviewCapacityResponse> {
    const searchParams = new URLSearchParams({
      difficulty: params.difficulty,
      mainQuestionCount: String(params.mainQuestionCount),
    });
    if (params.category?.trim()) {
      searchParams.set('category', params.category.trim());
    }
    return request.get<KnowledgeBaseInterviewCapacityResponse>(
      `/api/knowledgebase/${id}/interview-capacity?${searchParams.toString()}`
    );
  },

  /**
   * 基于知识库回答问题
   */
  async queryKnowledgeBase(req: QueryRequest): Promise<QueryResponse> {
    return request.post<QueryResponse>('/api/knowledgebase/query', req, {
      timeout: 180000, // 3分钟超时
    });
  },

  /**
   * 基于知识库回答问题（流式SSE）
   * 注意：SSE 使用 fetch API，不走统一的 axios 封装
   */
  async queryKnowledgeBaseStream(
    req: QueryRequest,
    onMessage: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    return streamSse({
      url: '/api/knowledgebase/query/stream',
      init: {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(req),
      },
      onMessage,
      onComplete,
      onError,
      parseMode: 'line',
      trimDataPrefixSpace: true,
    });
  },
};
