// frontend/src/components/interviewschedule/InterviewListItem.tsx

import React from 'react';
import { motion } from 'framer-motion';
import { Edit2, Trash2, ExternalLink } from 'lucide-react';
import dayjs from 'dayjs';
import type { InterviewSchedule, InterviewStatus } from '../../types/interviewSchedule';

interface InterviewListItemProps {
  interview: InterviewSchedule;
  onEdit: () => void;
  onDelete: () => void;
  onStatusChange: (status: InterviewStatus) => void;
}

const statusConfig: Record<InterviewStatus, { label: string; className: string }> = {
  PENDING: {
    label: '待面试',
    className: 'bg-blue-500/10 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 border border-blue-300/30 dark:border-blue-400/30',
  },
  COMPLETED: {
    label: '已完成',
    className: 'bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-300/30 dark:border-emerald-400/30',
  },
  CANCELLED: {
    label: '已取消',
    className: 'bg-slate-500/10 dark:bg-slate-500/20 text-slate-700 dark:text-slate-300 border border-slate-300/30 dark:border-slate-400/30',
  },
  RESCHEDULED: {
    label: '已改期',
    className: 'bg-amber-500/10 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-300/30 dark:border-amber-400/30',
  },
};

const typeLabels: Record<string, string> = {
  ONSITE: '现场面试',
  VIDEO: '视频面试',
  PHONE: '电话面试',
};

export const InterviewListItem: React.FC<InterviewListItemProps> = ({
  interview,
  onEdit,
  onDelete,
  onStatusChange,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className="rounded-2xl border border-slate-200/50 bg-white/90 p-4 backdrop-blur-xl transition-all hover:-translate-y-0.5 hover:shadow-2xl hover:shadow-slate-200/50 dark:border-slate-700/50 dark:bg-slate-900/90 dark:hover:shadow-slate-900/50 sm:p-6"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <span className={`status-badge backdrop-blur-sm ${statusConfig[interview.status].className}`}>
              {statusConfig[interview.status].label}
            </span>
            <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
              {dayjs(interview.interviewTime).format('YYYY-MM-DD HH:mm')}
            </span>
          </div>

          <h3 className="font-display font-bold text-xl mb-2 text-slate-900 dark:text-white tracking-tight">
            {interview.companyName}
          </h3>
          <p className="text-slate-600 dark:text-slate-300 mb-3 font-medium">{interview.position}</p>

          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
            <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg font-medium">
              第 {interview.roundNumber} 轮
            </span>
            <span className="text-slate-300 dark:text-slate-600">•</span>
            <span className="font-medium">{typeLabels[interview.interviewType] || interview.interviewType}</span>
            {interview.interviewer && (
              <>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span className="font-medium">{interview.interviewer}</span>
              </>
            )}
          </div>

          {interview.meetingLink && (
            <motion.a
              whileHover={{ x: 2 }}
              href={interview.meetingLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 mt-3 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              进入会议
            </motion.a>
          )}

          {interview.notes && (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-3 italic">{interview.notes}</p>
          )}
        </div>

        <div className="flex gap-2 self-end sm:self-auto">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={onEdit}
            aria-label="编辑面试"
            className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-400 transition-all hover:bg-primary-500/10 hover:text-primary-600 hover:shadow-lg hover:shadow-primary-500/20 dark:text-slate-500 dark:hover:bg-primary-500/20 dark:hover:text-primary-400"
            title="编辑"
          >
            <Edit2 className="w-5 h-5" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={onDelete}
            aria-label="删除面试"
            className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-400 transition-all hover:bg-red-500/10 hover:text-red-600 hover:shadow-lg hover:shadow-red-500/20 dark:text-slate-500 dark:hover:bg-red-500/20 dark:hover:text-red-400"
            title="删除"
          >
            <Trash2 className="w-5 h-5" />
          </motion.button>
        </div>
      </div>

      {interview.status === 'PENDING' && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 flex flex-col gap-3 border-t border-slate-200 pt-4 dark:border-slate-700 sm:flex-row"
        >
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onStatusChange('COMPLETED')}
            className="min-h-11 flex-1 rounded-xl border border-emerald-300/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-700 transition-all hover:bg-emerald-500/20 dark:border-emerald-400/30 dark:bg-emerald-500/20 dark:text-emerald-300 dark:hover:bg-emerald-500/30"
          >
            标记为已完成
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onStatusChange('CANCELLED')}
            className="min-h-11 flex-1 rounded-xl border border-slate-300/30 bg-slate-500/10 px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-slate-500/20 dark:border-slate-400/30 dark:bg-slate-500/20 dark:text-slate-300 dark:hover:bg-slate-500/30"
          >
            取消面试
          </motion.button>
        </motion.div>
      )}
    </motion.div>
  );
};
