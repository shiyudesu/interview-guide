import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertCircle, Loader2, Play } from 'lucide-react';
import type {
  KnowledgeBaseInterviewCapacityResponse,
  KnowledgeBaseItem,
} from '../../api/knowledgebase';
import { knowledgeBaseApi } from '../../api/knowledgebase';
import {
  DEFAULT_DIFFICULTY,
  DIFFICULTY_OPTIONS,
  FOLLOW_UP_COUNT_OPTIONS,
  INPUT_CLASS,
  MAIN_QUESTION_COUNT_OPTIONS,
} from '../../constants/knowledgebaseInterview';
import {
  getSelectedCapacity,
  getStrictCapacityMessage,
} from './interviewCapacity';
import ResponsiveDialog from '../ResponsiveDialog';

export interface StartInterviewConfig {
  category: string;  // 空字符串表示覆盖全部方向
  difficulty: string;
  mainQuestionCount: number;
  followUpCount: number;
}

interface StartKnowledgeBaseInterviewModalProps {
  open: boolean;
  knowledgeBase: KnowledgeBaseItem | null;
  defaultDifficulty?: string;
  starting: boolean;
  error: string;
  onClose: () => void;
  onStart: (config: StartInterviewConfig) => void;
}

export default function StartKnowledgeBaseInterviewModal({
  open,
  knowledgeBase,
  defaultDifficulty = DEFAULT_DIFFICULTY,
  starting,
  error,
  onClose,
  onStart,
}: StartKnowledgeBaseInterviewModalProps) {
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [mainQuestionCount, setMainQuestionCount] = useState(5);
  const [followUpCount, setFollowUpCount] = useState(1);
  const [capacity, setCapacity] =
    useState<KnowledgeBaseInterviewCapacityResponse | null>(null);
  const [loadingCapacity, setLoadingCapacity] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!open || !knowledgeBase) {
      setCapacity(null);
      setLoadError('');
      return;
    }
    setCategory('');
    setDifficulty(defaultDifficulty);
    setMainQuestionCount(5);
    setFollowUpCount(1);
  }, [open, knowledgeBase, defaultDifficulty]);

  useEffect(() => {
    if (!open || !knowledgeBase) return;
    let cancelled = false;
    setLoadingCapacity(true);
    setCapacity(null);
    setLoadError('');
    knowledgeBaseApi
      .getInterviewCapacity(knowledgeBase.id, {
        category: category || undefined,
        difficulty,
        mainQuestionCount,
      })
      .then(result => {
        if (cancelled) return;
        setCapacity(result);
      })
      .catch(err => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : '加载面试容量失败');
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCapacity(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, knowledgeBase, category, difficulty, mainQuestionCount]);

  const followUpOptions = capacity?.followUpOptions ?? [];
  const selectedCapacity = getSelectedCapacity(followUpOptions, followUpCount);
  const availableCount = selectedCapacity?.availableQuestionCount ?? 0;
  const canStart = selectedCapacity?.selectable === true && !loadingCapacity;
  const categoryOptions = capacity?.categories ?? [];
  const selectedCategoryMissing = category
    && !categoryOptions.some(option => option.category === category);

  const footer = (
    <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
      <button
        type="button"
        onClick={onClose}
        disabled={starting}
        className="min-h-11 rounded-xl border border-slate-200 px-5 py-2.5 font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
      >取消</button>
      <motion.button
        type="button"
        onClick={() => onStart({ category, difficulty, mainQuestionCount, followUpCount })}
        disabled={!canStart || starting || loadingCapacity}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 px-5 py-2.5 font-semibold text-white shadow-lg transition-all hover:from-primary-600 hover:to-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {starting ? '创建中…' : '开始面试'}
      </motion.button>
    </div>
  );

  return (
    <ResponsiveDialog
      open={open}
      onClose={onClose}
      closeDisabled={starting}
      size="md"
      title={(
        <div className="flex min-w-0 items-center gap-2">
          <Play className="h-5 w-5 flex-shrink-0 text-primary-500" />
          <div className="min-w-0">
            <h3 className="text-lg font-bold">开始知识库面试</h3>
            <p className="truncate text-xs font-normal text-slate-500 dark:text-slate-400">
              仅从 <span className="font-medium">{knowledgeBase?.name}</span> 的已启用题目抽题
            </p>
          </div>
        </div>
      )}
      footer={footer}
    >
      <div className="space-y-4">
                <label className="block">
                  <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">面试方向</span>
                  <select
                    value={category}
                    onChange={event => setCategory(event.target.value)}
                    className={INPUT_CLASS}
                    disabled={loadingCapacity}
                  >
                    <option value="">全部方向</option>
                    {selectedCategoryMissing && (
                      <option value={category}>{category}（当前难度 0 题）</option>
                    )}
                    {categoryOptions.map(item => (
                      <option key={item.category} value={item.category}>
                        {item.category}（{item.availableQuestionCount} 题）
                      </option>
                    ))}
                  </select>
                </label>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <label className="block">
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">难度</span>
                    <select
                      value={difficulty}
                      onChange={event => setDifficulty(event.target.value)}
                      className={INPUT_CLASS}
                    >
                      {DIFFICULTY_OPTIONS.map(option => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">主问题数</span>
                    <select
                      value={mainQuestionCount}
                      onChange={event => setMainQuestionCount(parseInt(event.target.value, 10))}
                      className={INPUT_CLASS}
                    >
                      {MAIN_QUESTION_COUNT_OPTIONS.map(count => (
                        <option key={count} value={count}>{count} 道</option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">每道主问题最多追问</span>
                    <select
                      value={followUpCount}
                      onChange={event => setFollowUpCount(parseInt(event.target.value, 10))}
                      className={INPUT_CLASS}
                    >
                      {FOLLOW_UP_COUNT_OPTIONS.map(count => {
                        const optionCapacity = getSelectedCapacity(followUpOptions, count);
                        const label = optionCapacity
                          ? `${count} 次（${optionCapacity.availableQuestionCount} 道主问题可用）`
                          : `${count} 次`;
                        return (
                          <option
                            key={count}
                            value={count}
                            disabled={!optionCapacity?.selectable}
                          >
                            {label}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                </div>

                <div className="rounded-lg bg-slate-50 dark:bg-slate-900 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                  {loadingCapacity ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" /> 正在统计可用题目…
                    </span>
                  ) : (
                    <>
                      当前条件可用{' '}
                      <span className={`font-bold ${canStart ? 'text-primary-600 dark:text-primary-400' : 'text-red-500'}`}>
                        {availableCount}
                      </span>{' '}
                      道主问题
                      {!canStart && (
                        <span className="block mt-1 text-xs text-red-500">
                          {getStrictCapacityMessage(
                            followUpOptions,
                            followUpCount,
                            mainQuestionCount
                          )}
                        </span>
                      )}
                    </>
                  )}
                  {loadError && <p className="mt-1 text-xs text-red-500">{loadError}</p>}
                </div>

                {error && (
                  <div className="flex items-start gap-2 text-sm text-red-500">
                    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
      </div>
    </ResponsiveDialog>
  );
}
