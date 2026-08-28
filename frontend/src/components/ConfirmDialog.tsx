import {motion} from 'framer-motion';
import ResponsiveDialog from './ResponsiveDialog';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string | React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: 'danger' | 'primary' | 'warning';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
  customContent?: React.ReactNode;
  hideButtons?: boolean;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmText = '确定',
  cancelText = '取消',
  confirmVariant = 'primary',
  onConfirm,
  onCancel,
  loading = false,
  customContent,
  hideButtons = false
}: ConfirmDialogProps) {
  const variantStyles = {
    danger: 'bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700',
    primary: 'bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700',
    warning: 'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600'
  };

  const footer = hideButtons ? undefined : (
    <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
      <motion.button
        onClick={onCancel}
        disabled={loading}
        className="min-h-11 w-full rounded-xl border border-slate-200 px-5 py-2.5 font-medium text-slate-600 transition-all hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        {cancelText}
      </motion.button>
      <motion.button
        onClick={onConfirm}
        disabled={loading}
        className={`min-h-11 w-full rounded-xl px-5 py-2.5 font-semibold text-white shadow-lg transition-all disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto ${variantStyles[confirmVariant]}`}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <motion.span
              className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            处理中...
          </span>
        ) : confirmText}
      </motion.button>
    </div>
  );

  return (
    <ResponsiveDialog
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      mobileMode="compact"
      closeDisabled={loading}
      footer={footer}
    >
      <div className="text-slate-600 dark:text-slate-300">
        {typeof message === 'string' ? (
          message && <p className="whitespace-pre-line">{message}</p>
        ) : message}
        {customContent}
      </div>
    </ResponsiveDialog>
  );
}
