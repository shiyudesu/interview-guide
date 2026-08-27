import { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Server } from 'lucide-react';

export interface ProviderDropdownOption {
  value: string;
  name: string;
  description?: string;
  badge?: string;
  disabled?: boolean;
}

interface ProviderDropdownProps {
  ariaLabel: string;
  value: string;
  options: ProviderDropdownOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  tone?: 'primary' | 'emerald';
}

const TONE_CLASSES = {
  primary: {
    focus: 'focus-visible:border-primary-400 focus-visible:ring-primary-500/20',
    icon: 'bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300',
    selected: 'border-primary-100 bg-primary-50/80 dark:border-primary-900/50 dark:bg-primary-900/20',
    check: 'bg-primary-500 text-white',
    badge: 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300',
  },
  emerald: {
    focus: 'focus-visible:border-emerald-400 focus-visible:ring-emerald-500/20',
    icon: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300',
    selected: 'border-emerald-100 bg-emerald-50/80 dark:border-emerald-900/50 dark:bg-emerald-900/20',
    check: 'bg-emerald-500 text-white',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  },
} as const;

export default function ProviderDropdown({
  ariaLabel,
  value,
  options,
  onChange,
  placeholder = '请选择 Provider',
  disabled = false,
  tone = 'primary',
}: ProviderDropdownProps) {
  const listboxId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const selectedOption = options.find(option => option.value === value) ?? null;
  const colors = TONE_CLASSES[tone];

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(current => !current)}
        className={`flex min-h-[58px] w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-left shadow-sm transition
          hover:border-slate-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-4
          disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 ${colors.focus}`}
      >
        <span className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${colors.icon}`}>
          <Server className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-800 dark:text-white">
              {selectedOption?.name ?? placeholder}
            </span>
            {selectedOption?.badge && (
              <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${colors.badge}`}>
                {selectedOption.badge}
              </span>
            )}
          </span>
          {selectedOption?.description && (
            <span className="mt-0.5 block truncate text-xs text-slate-500 dark:text-slate-400">
              {selectedOption.description}
            </span>
          )}
        </span>
        {open
          ? <ChevronUp className="h-4 w-4 flex-shrink-0 text-slate-400" />
          : <ChevronDown className="h-4 w-4 flex-shrink-0 text-slate-400" />
        }
      </button>

      {open && (
        <div
          id={listboxId}
          role="listbox"
          aria-label={ariaLabel}
          className="absolute z-40 mt-2 max-h-72 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-900/10 dark:border-slate-700 dark:bg-slate-800 dark:shadow-black/30"
        >
          {options.map(option => {
            const selected = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={selected}
                disabled={option.disabled}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors
                  ${selected
                    ? colors.selected
                    : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-700/70'
                  }
                  disabled:cursor-not-allowed disabled:opacity-45`}
              >
                <span className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${selected ? colors.icon : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'}`}>
                  <Server className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{option.name}</span>
                    {option.badge && (
                      <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${selected ? colors.badge : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'}`}>
                        {option.badge}
                      </span>
                    )}
                  </span>
                  {option.description && (
                    <span className="mt-0.5 block truncate text-xs text-slate-500 dark:text-slate-400">
                      {option.description}
                    </span>
                  )}
                </span>
                <span className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full ${selected ? colors.check : 'text-transparent'}`}>
                  <Check className="h-3 w-3" />
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
