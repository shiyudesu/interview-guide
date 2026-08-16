import type { KnowledgeBaseQuestionStatus } from '../api/knowledgebase';

export interface StatusOption {
  value: KnowledgeBaseQuestionStatus | '';
  label: string;
}

export const STATUS_OPTIONS: StatusOption[] = [
  { value: '', label: '全部' },
  { value: 'DRAFT', label: '草稿' },
  { value: 'ACTIVE', label: '已启用' },
  { value: 'ARCHIVED', label: '已归档' },
  { value: 'STALE', label: '已过期' },
];

export interface DifficultyOption {
  value: string;
  label: string;
}

export const DIFFICULTY_OPTIONS: DifficultyOption[] = [
  { value: 'junior', label: '校招' },
  { value: 'mid', label: '中级' },
  { value: 'senior', label: '高级' },
];

export const MAIN_QUESTION_COUNT_OPTIONS = [1, 3, 5, 8, 10];
export const FOLLOW_UP_COUNT_OPTIONS = [0, 1, 2, 3];
export const GENERATE_COUNT_OPTIONS = [3, 5, 10, 15];
export const CATEGORY_LIMIT_OPTIONS = [1, 2, 3, 5];

export const INPUT_CLASS =
  'w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 '
  + 'bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white '
  + 'focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500';

export const DEFAULT_DIFFICULTY = 'mid';
export const DEFAULT_CATEGORY_LIMIT = 3;

export function getStatusLabel(status: KnowledgeBaseQuestionStatus): string {
  return STATUS_OPTIONS.find(item => item.value === status)?.label || status;
}

export function getDifficultyLabel(difficulty: string): string {
  return DIFFICULTY_OPTIONS.find(item => item.value === difficulty)?.label || difficulty;
}
