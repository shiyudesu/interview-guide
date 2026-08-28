import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2, Sparkles } from 'lucide-react';
import {
  CATEGORY_LIMIT_OPTIONS,
  DEFAULT_CATEGORY_LIMIT,
  DEFAULT_DIFFICULTY,
  DIFFICULTY_OPTIONS,
  FOLLOW_UP_COUNT_OPTIONS,
  GENERATE_COUNT_OPTIONS,
  INPUT_CLASS,
} from '../../constants/knowledgebaseInterview';
import ResponsiveDialog from '../ResponsiveDialog';

export interface GenerateQuestionsConfig {
  difficulty: string;
  questionCount: number;
  followUpCount: number;
  categoryLimit: number;
}

interface GenerateKnowledgeBaseQuestionsModalProps {
  open: boolean;
  knowledgeBaseName: string;
  defaultDifficulty?: string;
  defaultCategoryLimit?: number;
  initialConfig?: GenerateQuestionsConfig | null;
  submitting: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (config: GenerateQuestionsConfig) => void;
}

export default function GenerateKnowledgeBaseQuestionsModal({
  open,
  knowledgeBaseName,
  defaultDifficulty = DEFAULT_DIFFICULTY,
  defaultCategoryLimit = DEFAULT_CATEGORY_LIMIT,
  initialConfig,
  submitting,
  error,
  onClose,
  onSubmit,
}: GenerateKnowledgeBaseQuestionsModalProps) {
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [questionCount, setQuestionCount] = useState(5);
  const [followUpCount, setFollowUpCount] = useState(2);
  const [categoryLimit, setCategoryLimit] = useState(defaultCategoryLimit);

  useEffect(() => {
    if (open) {
      setDifficulty(initialConfig?.difficulty || defaultDifficulty);
      setQuestionCount(initialConfig?.questionCount || 5);
      setFollowUpCount(initialConfig?.followUpCount ?? 2);
      setCategoryLimit(initialConfig?.categoryLimit || defaultCategoryLimit);
    }
  }, [open, defaultDifficulty, defaultCategoryLimit, initialConfig]);

  const footer = (
    <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
      <button type="button" onClick={onClose} disabled={submitting} className="min-h-11 rounded-xl border border-slate-200 px-5 py-2.5 font-medium text-slate-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300">取消</button>
      <motion.button
        type="button"
        onClick={() => onSubmit({ difficulty, questionCount, followUpCount, categoryLimit })}
        disabled={submitting}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 px-5 py-2.5 font-semibold text-white shadow-lg transition-all disabled:opacity-50"
      >
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        {submitting ? '提交中…' : '开始生成'}
      </motion.button>
    </div>
  );

  return (
    <ResponsiveDialog
      open={open}
      onClose={onClose}
      closeDisabled={submitting}
      title={<span className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary-500" />生成题目</span>}
      size="sm"
      footer={footer}
    >
      <div className="space-y-4">
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  基于知识库 <span className="font-semibold text-slate-700 dark:text-slate-200">{knowledgeBaseName}</span> 的内容，
                  按难度和方向生成草稿题。面试方向由模型基于知识库内容自动归类，并优先复用已有方向。
                </p>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">题量</span>
                    <select
                      value={questionCount}
                      onChange={event => setQuestionCount(parseInt(event.target.value, 10))}
                      className={INPUT_CLASS}
                    >
                      {GENERATE_COUNT_OPTIONS.map(count => (
                        <option key={count} value={count}>{count} 题</option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
                      方向上限
                    </span>
                    <select
                      value={categoryLimit}
                      onChange={event => setCategoryLimit(parseInt(event.target.value, 10))}
                      className={INPUT_CLASS}
                    >
                      {CATEGORY_LIMIT_OPTIONS.map(count => (
                        <option key={count} value={count}>{count} 个</option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
                      每题追问数
                    </span>
                    <select
                      value={followUpCount}
                      onChange={event => setFollowUpCount(parseInt(event.target.value, 10))}
                      className={INPUT_CLASS}
                    >
                      {FOLLOW_UP_COUNT_OPTIONS.map(count => (
                        <option key={count} value={count}>{count} 个</option>
                      ))}
                    </select>
                  </label>
                </div>

                {error && <p className="text-sm text-red-500">{error}</p>}
      </div>
    </ResponsiveDialog>
  );
}
