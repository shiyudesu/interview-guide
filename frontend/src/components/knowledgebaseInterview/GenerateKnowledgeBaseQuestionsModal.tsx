import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2, Sparkles, X } from 'lucide-react';
import {
  CATEGORY_LIMIT_OPTIONS,
  DEFAULT_CATEGORY_LIMIT,
  DEFAULT_DIFFICULTY,
  DIFFICULTY_OPTIONS,
  FOLLOW_UP_COUNT_OPTIONS,
  GENERATE_COUNT_OPTIONS,
  INPUT_CLASS,
} from '../../constants/knowledgebaseInterview';

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

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={e => e.stopPropagation()}
              className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-md w-full"
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-700">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary-500" />
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">生成题目</h3>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="px-6 py-5 space-y-4">
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  基于知识库 <span className="font-semibold text-slate-700 dark:text-slate-200">{knowledgeBaseName}</span> 的内容，
                  按难度和方向生成草稿题。面试方向由模型基于知识库内容自动归类，并优先复用已有方向。
                </p>

                <div className="grid grid-cols-2 gap-3">
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

                <div className="grid grid-cols-2 gap-3">
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

              <div className="flex gap-3 justify-end px-6 py-4 border-t border-slate-100 dark:border-slate-700">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  className="px-5 py-2.5 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 rounded-xl font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                  取消
                </button>
                <motion.button
                  type="button"
                  onClick={() => onSubmit({ difficulty, questionCount, followUpCount, categoryLimit })}
                  disabled={submitting}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="px-5 py-2.5 inline-flex items-center gap-2 text-white rounded-xl font-semibold shadow-lg bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {submitting ? '提交中…' : '开始生成'}
                </motion.button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
