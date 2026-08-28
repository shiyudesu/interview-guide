import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { KeyRound, Loader2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { getErrorMessage } from '../api/request';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(token ? '' : '重置链接缺少 Token');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await authApi.confirmPasswordReset(token, password);
      setSuccess(true);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900 sm:p-8">
        <div className="mb-5 flex items-center gap-3">
          <div className="rounded-xl bg-primary-100 p-3 text-primary-600"><KeyRound className="h-5 w-5" /></div>
          <div><h1 className="text-xl font-bold text-slate-900 dark:text-white">设置新密码</h1><p className="text-sm text-slate-500">密码至少 6 个字符</p></div>
        </div>
        {success ? (
          <div>
            <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-700">密码已重置，所有旧 Session 均已撤销。</div>
            <Link to="/login" className="mt-5 flex w-full justify-center rounded-xl bg-primary-600 px-4 py-3 font-semibold text-white">返回登录</Link>
          </div>
        ) : (
          <>
            {error && <div role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
            <div className="space-y-4">
              <label className="block"><span className="mb-1.5 block text-sm text-slate-700 dark:text-slate-300">新密码</span><input type="password" required minLength={6} maxLength={128} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3.5 py-3 dark:border-slate-700 dark:bg-slate-800 dark:text-white" /></label>
              <label className="block"><span className="mb-1.5 block text-sm text-slate-700 dark:text-slate-300">确认新密码</span><input type="password" required minLength={6} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3.5 py-3 dark:border-slate-700 dark:bg-slate-800 dark:text-white" /></label>
            </div>
            <button type="submit" disabled={!token || submitting} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{submitting && <Loader2 className="h-4 w-4 animate-spin" />}重置密码</button>
          </>
        )}
      </form>
    </div>
  );
}
