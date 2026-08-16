export interface InterviewStatsItem {
  status: string;
  evaluateStatus?: string | null;
  overallScore: number | null;
}

export interface InterviewStats {
  totalCount: number;
  completedCount: number;
  averageScore: number;
}

export function isCompletedStatus(status: string): boolean {
  return status === 'COMPLETED' || status === 'EVALUATED';
}

export function isEvaluateCompleted(item: InterviewStatsItem): boolean {
  return item.evaluateStatus === 'COMPLETED' || item.status === 'EVALUATED';
}

export function getKnowledgeBaseInterviewCategoryLabel(
  category?: string | null,
): string {
  return category?.trim() || '全部方向';
}

export function calculateInterviewStats<T extends InterviewStatsItem>(
  allItems: readonly T[],
  filteredItems: readonly T[],
  isKnowledgeBaseView: boolean,
): InterviewStats {
  const source = isKnowledgeBaseView ? filteredItems : allItems;
  const evaluated = source.filter(isEvaluateCompleted);
  const totalScore = evaluated.reduce((sum, item) => sum + (item.overallScore ?? 0), 0);

  return {
    totalCount: source.length,
    completedCount: evaluated.length,
    averageScore: evaluated.length > 0 ? Math.round(totalScore / evaluated.length) : 0,
  };
}
