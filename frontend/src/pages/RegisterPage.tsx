import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2, Sparkles, UserPlus } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { getErrorMessage } from '../api/request';

export default function RegisterPage() {
  const { register, registrationEnabled } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await register({ email, password, displayName: displayName.trim() || undefined });
      navigate('/settings', { replace: true });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center text-white">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-500 shadow-xl shadow-primary-500/30">
            <Sparkles className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold">创建账号</h1>
          <p className="mt-2 text-sm text-slate-300">使用你自己的模型 API Key，数据按账号隔离</p>
        </div>

        <form onSubmit={submit} className="rounded-2xl border border-white/10 bg-white p-7 shadow-2xl dark:bg-slate-900">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-xl bg-primary-50 p-2.5 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300">
              <UserPlus className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900 dark:text-white">注册新账号</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">密码至少 12 个字符</p>
            </div>
          </div>

          {!registrationEnabled && (
            <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
              当前未开放自助注册，请联系管理员创建账号。
            </div>
          )}
          {error && <div role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">显示名称（可选）</span>
              <input value={displayName} onChange={event => setDisplayName(event.target.value)} disabled={!registrationEnabled} autoComplete="name" className="w-full rounded-xl border border-slate-200 px-3.5 py-3 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">邮箱</span>
              <input type="email" required value={email} onChange={event => setEmail(event.target.value)} disabled={!registrationEnabled} autoComplete="email" className="w-full rounded-xl border border-slate-200 px-3.5 py-3 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">密码</span>
              <input type="password" minLength={12} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} disabled={!registrationEnabled} autoComplete="new-password" className="w-full rounded-xl border border-slate-200 px-3.5 py-3 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">确认密码</span>
              <input type="password" minLength={12} maxLength={128} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} disabled={!registrationEnabled} autoComplete="new-password" className="w-full rounded-xl border border-slate-200 px-3.5 py-3 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
            </label>
          </div>

          <button type="submit" disabled={!registrationEnabled || submitting} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 font-semibold text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50">
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            注册并继续
          </button>
          <p className="mt-5 text-center text-sm text-slate-500 dark:text-slate-400">
            已有账号？<Link to="/login" className="ml-1 font-medium text-primary-600 hover:text-primary-700">返回登录</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
