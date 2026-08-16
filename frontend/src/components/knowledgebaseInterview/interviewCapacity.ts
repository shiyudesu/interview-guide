import type { InterviewFollowUpCapacity } from '../../api/knowledgebase';

export function getSelectedCapacity(
  options: InterviewFollowUpCapacity[],
  followUpCount: number
): InterviewFollowUpCapacity | null {
  return options.find(option => option.followUpCount === followUpCount) ?? null;
}

export function getStrictCapacityMessage(
  options: InterviewFollowUpCapacity[],
  followUpCount: number,
  mainQuestionCount: number
): string {
  const selected = getSelectedCapacity(options, followUpCount);
  if (!selected) {
    return '暂时无法确认当前配置的可用题数，请稍后重试。';
  }
  if (selected.selectable) {
    return `当前条件可用 ${selected.availableQuestionCount} 道主问题。`;
  }
  const selectableOptions = options
    .filter(option => option.availableQuestionCount >= mainQuestionCount);
  if (selectableOptions.length === 0) {
    return `当前仅有 ${selected.availableQuestionCount} 道题包含至少 ${followUpCount} 个追问，`
      + `无法抽取 ${mainQuestionCount} 道主问题。`
      + '当前题量下没有足够的已启用主问题，请减少主问题数或补充题库。';
  }
  const maximumStrictCount = selectableOptions
    .reduce((maximum, option) => Math.max(maximum, option.followUpCount), 0);
  return `当前仅有 ${selected.availableQuestionCount} 道题包含至少 ${followUpCount} 个追问，`
    + `无法抽取 ${mainQuestionCount} 道主问题。`
    + `在当前题量下，每题最多可严格保证 ${maximumStrictCount} 个追问。`;
}

export function getFollowUpQualityWarning(
  actualCount: number,
  targetCount?: number | null
): string | null {
  if (targetCount == null || actualCount >= targetCount) {
    return null;
  }
  return `追问不足：实际 ${actualCount} / 目标 ${targetCount}`;
}
