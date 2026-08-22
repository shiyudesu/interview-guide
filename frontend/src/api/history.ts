import { request, type PageOptions } from './request';

export type AnalyzeStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
export type EvaluateStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface ResumeListOptions extends PageOptions {
  ids?: number[];
}

export interface ResumeListItem {
  id: number;
  filename: string;
  fileSize: number | null;
  uploadedAt: string;
  accessCount: number | null;
  latestScore: number | null;
  lastAnalyzedAt: string | null;
  interviewCount: number;
  analyzeStatus: AnalyzeStatus | null;
  analyzeError: string | null;
}

export interface AnalysisItem {
  id: number;
  overallScore: number | null;
  contentScore: number | null;
  structureScore: number | null;
  skillMatchScore: number | null;
  expressionScore: number | null;
  projectScore: number | null;
  summary: string | null;
  analyzedAt: string;
  strengths: string[];
  suggestions: Array<{
    category: string;
    priority: string;
    issue: string;
    recommendation: string;
  }>;
}

export interface InterviewItem {
  id: number;
  sessionId: string;
  channel: 'TEXT' | 'KNOWLEDGE_BASE' | 'VOICE';
  plannedMainQuestions: number;
  status: string | null;
  evaluateStatus: EvaluateStatus | null;
  evaluateError: string | null;
  overallScore: number | null;
  overallFeedback: string | null;
  createdAt: string;
  completedAt: string | null;
  strengths: string[];
  improvements: string[];
}

export interface AnswerItem {
  questionId: string;
  parentQuestionId: string | null;
  kind: 'MAIN' | 'FOLLOW_UP';
  question: string;
  category: string;
  userAnswer: string | null;
  score: number;
  feedback: string;
  referenceAnswer?: string;
  keyPoints?: string[];
  answeredAt: string | null;
}

export interface ResumeDetail {
  id: number;
  filename: string;
  fileSize: number | null;
  contentType: string | null;
  storageUrl: string | null;
  uploadedAt: string;
  accessCount: number | null;
  resumeText: string | null;
  analyzeStatus: AnalyzeStatus | null;
  analyzeError: string | null;
  analyses: AnalysisItem[];
  interviews: InterviewItem[];
}

export interface InterviewDetail extends InterviewItem {
  answers: AnswerItem[];
}

export const historyApi = {
  /**
   * 获取所有简历列表
   */
  async getResumes(options?: ResumeListOptions): Promise<ResumeListItem[]> {
    const params = new URLSearchParams();
    options?.ids?.forEach(id => params.append('ids', String(id)));
    if (options?.limit !== undefined) params.append('limit', String(options.limit));
    if (options?.offset !== undefined) params.append('offset', String(options.offset));
    return request.get<ResumeListItem[]>('/api/resumes', { params });
  },

  /**
   * 获取简历详情
   */
  async getResumeDetail(id: number): Promise<ResumeDetail> {
    return request.get<ResumeDetail>(`/api/resumes/${id}/detail`);
  },

  /**
   * 获取面试详情
   */
  async getInterviewDetail(sessionId: string): Promise<InterviewDetail> {
    return request.get<InterviewDetail>(`/api/interview/sessions/${sessionId}/details`);
  },

  /**
   * 导出简历分析报告PDF
   */
  async exportAnalysisPdf(resumeId: number): Promise<Blob> {
    return request.download(`/api/resumes/${resumeId}/export`);
  },

  /**
   * 导出面试报告PDF
   */
  async exportInterviewPdf(sessionId: string): Promise<Blob> {
    return request.download(`/api/interview/sessions/${sessionId}/export`);
  },

  /**
   * 删除简历
   */
  async deleteResume(id: number): Promise<void> {
    return request.delete(`/api/resumes/${id}`);
  },

  /**
   * 删除面试记录
   */
  async deleteInterview(sessionId: string): Promise<void> {
    return request.delete(`/api/interview/sessions/${sessionId}`);
  },

  /**
   * 重新分析简历
   */
  async reanalyze(id: number): Promise<void> {
    return request.post(`/api/resumes/${id}/reanalyze`);
  },
};
