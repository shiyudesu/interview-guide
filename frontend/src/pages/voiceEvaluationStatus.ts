export const VOICE_EVALUATION_RETRY_AFTER_MS = 2 * 60 * 1000;

export type VoiceEvaluationTone = 'loading' | 'warning' | 'error' | 'success';

export interface VoiceEvaluationPresentation {
  tone: VoiceEvaluationTone;
  label: string;
  title: string;
  description: string;
  retryable: boolean;
  shouldPoll: boolean;
}

interface VoiceEvaluationStatusInput {
  status?: string | null;
  statusUpdatedAt?: string | null;
  now?: number;
}

export function shouldRefreshVoiceEvaluationPresentation(
  status?: string | null,
): boolean {
  return status === 'PENDING' || status === 'PROCESSING';
}

function hasWaitedPastRetryThreshold(
  statusUpdatedAt: string | null | undefined,
  now: number,
): boolean {
  if (!statusUpdatedAt) return false;
  const updatedAt = new Date(statusUpdatedAt).getTime();
  return Number.isFinite(updatedAt)
    && now - updatedAt >= VOICE_EVALUATION_RETRY_AFTER_MS;
}

export function getVoiceEvaluationPresentation({
  status,
  statusUpdatedAt,
  now = Date.now(),
}: VoiceEvaluationStatusInput): VoiceEvaluationPresentation {
  if (status === 'FAILED') {
    return {
      tone: 'error',
      label: '生成失败',
      title: '评估报告生成失败',
      description: '本次面试记录已保存，你可以重新生成评估报告。',
      retryable: true,
      shouldPoll: false,
    };
  }

  if (status === 'COMPLETED') {
    return {
      tone: 'success',
      label: '已完成',
      title: '评估报告已生成',
      description: '本次面试的分析结果已经准备好。',
      retryable: false,
      shouldPoll: false,
    };
  }

  if (status === 'PROCESSING') {
    return {
      tone: 'loading',
      label: '评估中',
      title: 'AI 正在分析本次面试',
      description: '正在整理回答表现和改进建议，你可以先离开此页面。',
      retryable: false,
      shouldPoll: true,
    };
  }

  if (status === 'PENDING' && hasWaitedPastRetryThreshold(statusUpdatedAt, now)) {
    return {
      tone: 'warning',
      label: '评估延迟',
      title: '评估等待时间较长',
      description: '任务可能没有成功进入队列，你可以重新生成，已保存的面试记录不会丢失。',
      retryable: true,
      shouldPoll: true,
    };
  }

  return {
    tone: 'loading',
    label: '等待评估',
    title: '正在排队生成评估报告',
    description: '通常会在 10–30 秒内开始分析，你可以先离开此页面。',
    retryable: false,
    shouldPoll: true,
  };
}
