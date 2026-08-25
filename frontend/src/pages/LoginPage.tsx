import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Loader2, LockKeyhole, Sparkles } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { authApi } from '../api/auth';
import { getErrorMessage } from '../api/request';

interface LoginLocationState {
  from?: string;
  message?: string;
}

export default function LoginPage() {
  const { login, registrationEnabled } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const state = (location.state as LoginLocationState | null) ?? {};
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [verificationSent, setVerificationSent] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setVerificationSent(false);
    try {
      await login({ email, password });
      navigate(state.from || '/history', { replace: true });
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
          <h1 className="text-2xl font-bold">登录 AI Interview</h1>
          <p className="mt-2 text-sm text-slate-300">你的简历、面试记录和 API Key 仅属于当前账号</p>
        </div>

        <form onSubmit={submit} className="rounded-2xl border border-white/10 bg-white p-7 shadow-2xl dark:bg-slate-900">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-xl bg-primary-50 p-2.5 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900 dark:text-white">账号登录</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Session 保存在安全的 HttpOnly Cookie 中</p>
            </div>
          </div>

          {state.message && (
            <div className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300">
              {state.message}
            </div>
          )}
          {error && (
            <div role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              <p>{error}</p>
              {error.includes('邮箱尚未验证') && email && (
                <button
                  type="button"
                  className="mt-2 font-medium underline"
                  onClick={async () => {
                    try {
                      await authApi.requestEmailVerification(email);
                      setVerificationSent(true);
                    } catch (caught) {
                      setError(getErrorMessage(caught));
                    }
                  }}
                >
                  重新发送验证邮件
                </button>
              )}
              {verificationSent && <p className="mt-2 text-emerald-700">如果账号处于待验证状态，邮件已重新发送。</p>}
            </div>
          )}

          <label className="mb-4 block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">邮箱</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={event => setEmail(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              placeholder="you@example.com"
            />
          </label>

          <div className="mb-6 block">
            <label htmlFor="login-password" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">密码</label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={event => setPassword(event.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 pr-11 text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                placeholder="请输入密码"
              />
              <button
                type="button"
                onClick={() => setShowPassword(value => !value)}
                className="absolute inset-y-0 right-0 px-3 text-slate-400 hover:text-slate-600"
                aria-label={showPassword ? '隐藏密码' : '显示密码'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="-mt-3 mb-5 text-right">
            <Link to="/forgot-password" className="text-sm font-medium text-primary-600 hover:text-primary-700">忘记密码？</Link>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 px-4 py-3 font-semibold text-white shadow-lg shadow-primary-500/20 transition hover:from-primary-600 hover:to-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            登录
          </button>

          <p className="mt-5 text-center text-sm text-slate-500 dark:text-slate-400">
            {registrationEnabled ? (
              <>还没有账号？<Link to="/register" className="ml-1 font-medium text-primary-600 hover:text-primary-700">注册</Link></>
            ) : '当前由管理员创建账号，暂未开放自助注册'}
          </p>
        </form>
      </div>
    </div>
  );
}
