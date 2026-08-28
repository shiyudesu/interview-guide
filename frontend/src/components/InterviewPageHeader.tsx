import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface InterviewPageHeaderProps {
  title: string;
  subtitle: string;
  icon: ReactNode;
}

export default function InterviewPageHeader({
  title,
  subtitle,
  icon,
}: InterviewPageHeaderProps) {
  return (
    <motion.div
      className="mb-6 text-center sm:mb-8"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h1 className="mb-2 flex items-center justify-center gap-3 text-2xl font-bold text-slate-900 dark:text-white sm:text-3xl">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 sm:h-12 sm:w-12">
          {icon}
        </div>
        {title}
      </h1>
      <p className="px-2 text-sm text-slate-500 dark:text-slate-400 sm:text-base">{subtitle}</p>
    </motion.div>
  );
}
