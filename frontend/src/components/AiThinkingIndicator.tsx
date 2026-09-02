import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

interface AiThinkingIndicatorProps {
  label?: string;
  message?: string;
  slowMessage?: string;
  slowAfterMs?: number;
}

export default function AiThinkingIndicator({
  label = 'AI 助手',
  message = '正在思考',
  slowMessage = '仍在处理中，请稍候，不需要重复提交',
  slowAfterMs = 8000,
}: AiThinkingIndicatorProps) {
  const [takingLonger, setTakingLonger] = useState(false);

  useEffect(() => {
    setTakingLonger(false);
    const timer = window.setTimeout(() => setTakingLonger(true), slowAfterMs);
    return () => window.clearTimeout(timer);
  }, [slowAfterMs]);

  const statusMessage = takingLonger ? slowMessage : message;

  return (
    <motion.div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      data-testid="ai-thinking-indicator"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-3 sm:gap-4"
    >
      <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 ring-1 ring-primary-100 dark:bg-primary-950/70 dark:text-primary-300 dark:ring-primary-800/70">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">{label}</p>
        <div className="inline-flex max-w-full items-center gap-3 rounded-2xl rounded-tl-md border border-slate-200/80 bg-slate-50 px-4 py-3 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
          <span className="flex items-center gap-1" aria-hidden="true">
            {[0, 1, 2].map(index => (
              <span
                key={index}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-500"
                style={{ animationDelay: `-${index * 140}ms` }}
              />
            ))}
          </span>
          <span className="break-words">{statusMessage}</span>
        </div>
      </div>
    </motion.div>
  );
}
