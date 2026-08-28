import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';

type DialogSize = 'sm' | 'md' | 'lg' | 'xl';
type MobileMode = 'sheet' | 'compact';

interface ResponsiveDialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: DialogSize;
  mobileMode?: MobileMode;
  closeDisabled?: boolean;
  closeOnBackdrop?: boolean;
  bodyClassName?: string;
  panelClassName?: string;
  titleClassName?: string;
}

const SIZE_CLASSES: Record<DialogSize, string> = {
  sm: 'sm:max-w-md',
  md: 'sm:max-w-lg',
  lg: 'sm:max-w-2xl',
  xl: 'sm:max-w-4xl',
};

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export default function ResponsiveDialog({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  mobileMode = 'sheet',
  closeDisabled = false,
  closeOnBackdrop = true,
  bodyClassName = '',
  panelClassName = '',
  titleClassName = '',
}: ResponsiveDialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    const previousActiveElement = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusTimer = window.setTimeout(() => {
      const firstFocusable = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (firstFocusable ?? panelRef.current)?.focus();
    }, 0);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !closeDisabled) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousActiveElement?.focus();
    };
  }, [closeDisabled, open]);

  if (typeof document === 'undefined') return null;

  const mobileHeightClass = mobileMode === 'sheet'
    ? 'h-[calc(100dvh-1rem)] sm:h-auto'
    : 'h-auto';

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-2 sm:p-4">
          <motion.div
            className="absolute inset-0 h-full w-full cursor-default bg-black/55 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              if (closeOnBackdrop && !closeDisabled) onClose();
            }}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.97, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 24 }}
            transition={{ duration: 0.18 }}
            className={`relative flex w-full flex-col overflow-hidden rounded-2xl border border-slate-200/70 bg-white shadow-2xl outline-none dark:border-slate-700 dark:bg-slate-800 ${SIZE_CLASSES[size]} ${mobileHeightClass} max-h-[calc(100dvh-1rem)] sm:max-h-[90dvh] ${panelClassName}`}
          >
            <div className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-slate-100 px-4 py-4 sm:px-6 dark:border-slate-700">
              <div id={titleId} role="heading" aria-level={2} className={`min-w-0 text-lg font-bold text-slate-900 sm:text-xl dark:text-white ${titleClassName}`}>
                {title}
              </div>
              <button
                type="button"
                onClick={onClose}
                disabled={closeDisabled}
                aria-label="关闭"
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className={`min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6 ${bodyClassName}`}>
              {children}
            </div>
            {footer && (
              <div className="safe-area-bottom flex-shrink-0 border-t border-slate-100 bg-slate-50/90 px-4 py-4 sm:px-6 dark:border-slate-700 dark:bg-slate-900/50">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
