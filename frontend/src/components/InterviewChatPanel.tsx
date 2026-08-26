import {useEffect, useMemo, useRef, useState} from 'react';
import {motion} from 'framer-motion';
import {Virtuoso, type VirtuosoHandle} from 'react-virtuoso';
import type {InterviewQuestion, InterviewSession} from '../types/interview';
import {AlertCircle, ArrowDown, CheckCircle2, Send, Sparkles} from 'lucide-react';
import InterviewMessageBubble from './InterviewMessageBubble';

interface Message {
  type: 'interviewer' | 'user';
  content: string;
  category?: string | null;
  questionId?: string;
}

interface InterviewChatPanelProps {
  title: string;
  subtitle: string;
  session: InterviewSession;
  currentQuestion: InterviewQuestion | null;
  messages: Message[];
  answer: string;
  onAnswerChange: (answer: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  error?: string;
  onShowCompleteConfirm: (show: boolean) => void;
}

/**
 * 面试聊天面板组件
 */
export default function InterviewChatPanel({
  title,
  subtitle,
  session,
  currentQuestion,
  messages,
  answer,
  onAnswerChange,
  onSubmit,
  isSubmitting,
  error,
  onShowCompleteConfirm
}: InterviewChatPanelProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const progress = useMemo(() => {
    if (!session) return 0;
    const {completedMainQuestions, plannedMainQuestions} = session.progress;
    return plannedMainQuestions > 0
      ? (completedMainQuestions / plannedMainQuestions) * 100
      : 0;
  }, [session]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 72), 200)}px`;
  }, [answer]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onSubmit();
    }
  };

  const scrollToLatest = () => {
    if (messages.length === 0) return;
    virtuosoRef.current?.scrollToIndex({
      index: messages.length - 1,
      align: 'end',
      behavior: 'smooth',
    });
  };

  return (
    <section
      data-testid="interview-workspace"
      className="mx-auto flex h-[calc(100dvh-5rem)] min-h-[560px] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-xl shadow-slate-200/50 dark:border-slate-700 dark:bg-slate-900 dark:shadow-slate-950/40"
    >
      <header className="relative flex flex-shrink-0 items-center justify-between gap-4 border-b border-slate-100 bg-white/95 px-5 py-4 sm:px-7 dark:border-slate-800 dark:bg-slate-900/95">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary-600 text-white shadow-sm shadow-primary-500/25">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <h1 className="truncate text-base font-semibold text-slate-900 sm:text-lg dark:text-white">{title}</h1>
              <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                进行中
              </span>
            </div>
            <p className="hidden truncate text-xs text-slate-500 sm:block dark:text-slate-400">{subtitle}</p>
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-3">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              {session.progress.completedMainQuestions} / {session.progress.plannedMainQuestions}
            </p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">
              {currentQuestion?.kind === 'FOLLOW_UP' ? '针对性追问' : '主问题进度'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onShowCompleteConfirm(true)}
            disabled={isSubmitting}
            className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
          >
            <CheckCircle2 className="h-4 w-4" />
            <span className="hidden sm:inline">提前交卷</span>
          </button>
        </div>

        <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-slate-100 dark:bg-slate-800">
          <motion.div
            className="h-full bg-primary-500"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </header>

      <div className="relative min-h-0 flex-1 bg-white dark:bg-slate-900" data-testid="interview-message-list">
        <Virtuoso
          ref={virtuosoRef}
          data={messages}
          initialTopMostItemIndex={messages.length - 1}
          followOutput="smooth"
          atBottomStateChange={setIsAtBottom}
          className="h-full w-full scrollbar-thin"
          itemContent={(index, msg) => (
            <div className={`mx-auto max-w-4xl px-4 pb-7 sm:px-8 ${index === 0 ? 'pt-8' : ''}`}>
              <InterviewMessageBubble
                role={msg.type === 'interviewer' ? 'interviewer' : 'user'}
                text={msg.content}
                category={msg.category ?? undefined}
                appearance="conversation"
              />
            </div>
          )}
        />

        {!isAtBottom && (
          <button
            type="button"
            onClick={scrollToLatest}
            aria-label="回到最新消息"
            title="回到最新消息"
            className="absolute bottom-3 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-lg transition hover:text-primary-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}
      </div>

      <footer className="flex-shrink-0 bg-gradient-to-t from-white via-white to-white/90 px-4 pb-4 pt-2 sm:px-8 sm:pb-6 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900/90">
        <div className="mx-auto max-w-4xl">
          {error && (
            <div className="mb-2 flex items-center gap-2 px-2 text-sm text-red-600 dark:text-red-400" role="alert">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div
            data-testid="interview-composer"
            className="rounded-[24px] border border-slate-200 bg-slate-50/90 p-3 shadow-sm transition focus-within:border-primary-300 focus-within:bg-white focus-within:shadow-md focus-within:ring-4 focus-within:ring-primary-500/5 dark:border-slate-700 dark:bg-slate-800/90 dark:focus-within:border-primary-700 dark:focus-within:bg-slate-800"
          >
            <textarea
              ref={textareaRef}
              value={answer}
              onChange={(e) => onAnswerChange(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="输入你的回答..."
              className="block min-h-[72px] max-h-[200px] w-full resize-none overflow-y-auto bg-transparent px-2 py-1 text-[15px] leading-6 text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed dark:text-white dark:placeholder:text-slate-500"
              rows={1}
              disabled={isSubmitting}
            />

            <div className="mt-2 flex items-center justify-between gap-3 border-t border-slate-200/80 px-1 pt-3 dark:border-slate-700/80">
              <span className="text-xs text-slate-400 dark:text-slate-500">
                Ctrl / Cmd + Enter 提交
              </span>
              <motion.button
                type="button"
                onClick={onSubmit}
                disabled={!answer.trim() || isSubmitting}
                aria-label={isSubmitting ? '正在提交回答' : '提交回答'}
                title={isSubmitting ? '正在提交回答' : '提交回答'}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-600 text-white shadow-sm transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 dark:disabled:bg-slate-700 dark:disabled:text-slate-500"
                whileHover={{ scale: isSubmitting || !answer.trim() ? 1 : 1.02 }}
                whileTap={{ scale: isSubmitting || !answer.trim() ? 1 : 0.98 }}
              >
                {isSubmitting ? (
                  <motion.div
                    className="h-4 w-4 rounded-full border-2 border-current border-t-transparent"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </motion.button>
            </div>
          </div>

          <p className="mt-2 text-center text-[11px] text-slate-400 dark:text-slate-600">
            回答会用于生成本次模拟面试评估，请避免填写敏感信息
          </p>
        </div>
      </footer>
    </section>
  );
}
