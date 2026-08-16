import type {
  QuestionGenStatus,
  QuestionGenStatusResponse,
} from '../api/knowledgebase';

export interface QuestionGenerationNotice {
  tone: 'info' | 'success' | 'warning' | 'error';
  text: string;
}

type NoticeSource = Pick<
  QuestionGenStatusResponse,
  'questionGenStatus' | 'savedCount' | 'skippedCount'
> & Partial<Pick<QuestionGenStatusResponse, 'message' | 'error'>>;

export function isQuestionGenerationActive(status?: QuestionGenStatus | null): boolean {
  return status === 'QUEUED' || status === 'PROCESSING';
}

export function shouldRefreshGeneratedQuestions(
  previousStatus: QuestionGenStatus | null | undefined,
  nextStatus: QuestionGenStatus,
  sameTask: boolean
): boolean {
  return sameTask
    && isQuestionGenerationActive(previousStatus)
    && nextStatus === 'COMPLETED';
}

export function getQuestionGenerationNotice(
  status: NoticeSource
): QuestionGenerationNotice | null {
  switch (status.questionGenStatus) {
    case 'QUEUED':
      return { tone: 'info', text: '任务已提交，正在等待生成题目…' };
    case 'PROCESSING':
      return { tone: 'info', text: '正在生成题目，期间可以继续管理已有题目…' };
    case 'COMPLETED':
      return {
        tone: status.skippedCount > 0 ? 'warning' : 'success',
        text: status.message
          || `已生成 ${status.savedCount} 道题，跳过 ${status.skippedCount} 道题`,
      };
    case 'FAILED':
      return { tone: 'error', text: '题目生成失败，请稍后重试' };
    case 'NONE':
    default:
      return null;
  }
}
