import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronUp, Server } from 'lucide-react';
import type { ProviderItem } from '../types/llmProvider';
import ProviderDropdown from './ProviderDropdown';

interface InterviewProviderSelectorProps {
  providers: ProviderItem[];
  defaultProviderId: string;
  value: string;
  loading: boolean;
  onChange: (providerId: string) => void;
}

export default function InterviewProviderSelector({
  providers,
  defaultProviderId,
  value,
  loading,
  onChange,
}: InterviewProviderSelectorProps) {
  const [expanded, setExpanded] = useState(false);
  const effectiveProviderId = value || defaultProviderId;
  const defaultProvider = providers.find(provider => provider.id === defaultProviderId) ?? null;
  const effectiveProvider = providers.find(provider => provider.id === effectiveProviderId) ?? null;
  const configuredProviders = providers.filter(provider => provider.hasApiKey);
  const providerOptions = [
    {
      value: '',
      name: '账号默认',
      description: defaultProvider
        ? `${defaultProvider.id} · ${defaultProvider.model}`
        : defaultProviderId || '尚未配置默认 Provider',
      badge: '默认',
    },
    ...providers.filter(provider => provider.id !== defaultProviderId).map(provider => ({
      value: provider.id,
      name: provider.id,
      description: provider.model,
      badge: provider.hasApiKey ? undefined : '未配置 Key',
      disabled: !provider.hasApiKey,
    })),
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-900/40">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary-100 text-primary-600 dark:bg-primary-900/40 dark:text-primary-300">
          <Server className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800 dark:text-white">本次模型服务</p>
          {loading ? (
            <p className="mt-0.5 text-xs text-slate-400">正在读取账号默认 Provider...</p>
          ) : effectiveProvider ? (
            <>
              <p className="mt-0.5 truncate text-sm font-medium text-primary-700 dark:text-primary-300">
                {effectiveProvider.id} · {effectiveProvider.model}
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {value ? '仅本次面试覆盖账号默认设置' : '跟随账号默认设置'}
              </p>
            </>
          ) : (
            <p className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
              暂未读取到可用的默认 Provider
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setExpanded(current => !current)}
          disabled={loading}
          aria-expanded={expanded}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-primary-600 transition-colors hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-50 dark:text-primary-300 dark:hover:bg-primary-900/30"
        >
          {expanded ? '收起' : '更换'}
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-700">
          <p className="mb-2 block text-xs font-semibold text-slate-600 dark:text-slate-300">
            本次面试 Provider
          </p>
          <ProviderDropdown
            ariaLabel="本次面试 Provider"
            value={value}
            options={providerOptions}
            onChange={onChange}
            disabled={loading || providers.length === 0}
          />
          <div className="mt-2 flex items-start justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
            <p>用于出题、追问和评估；语音识别与合成仍使用语音服务配置。</p>
            <Link to="/settings" className="flex-shrink-0 font-medium text-primary-600 hover:text-primary-700 dark:text-primary-300">
              管理 Provider
            </Link>
          </div>
          {configuredProviders.length === 0 && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              尚未配置带 API Key 的 Provider，请先前往设置完成配置。
            </p>
          )}
        </div>
      )}

      {!loading && effectiveProvider && !effectiveProvider.hasApiKey && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
          当前 Provider 尚未配置 API Key，开始面试前请前往设置完成配置。
        </p>
      )}
    </div>
  );
}
