import type { EvaluateStatus } from '../api/history';

export type KnowledgeBaseInterviewCompletion =
  | { kind: 'waiting' }
  | { kind: 'completed'; path: string }
  | { kind: 'failed' };

export function resolveKnowledgeBaseInterviewCompletion(
  evaluateStatus: EvaluateStatus | undefined,
  knowledgeBaseId: number,
  sessionId: string,
): KnowledgeBaseInterviewCompletion {
  if (evaluateStatus === 'COMPLETED') {
    return {
      kind: 'completed',
      path: `/knowledgebase-interview/${knowledgeBaseId}/interviews/${sessionId}`,
    };
  }
  if (evaluateStatus === 'FAILED') {
    return { kind: 'failed' };
  }
  return { kind: 'waiting' };
}
