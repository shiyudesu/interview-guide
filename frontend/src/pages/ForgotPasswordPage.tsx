import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Mail } from 'lucide-react';
import { authApi } from '../api/auth';
import { getErrorMessage } from '../api/request';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await authApi.requestPasswordReset(email);
      setMessage('如果该邮箱对应可用账号，密码重置邮件已经发送。');
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
          <div className="rounded-xl bg-primary-100 p-3 text-primary-600"><Mail className="h-5 w-5" /></div>
          <div><h1 className="text-xl font-bold text-slate-900 dark:text-white">找回密码</h1><p className="text-sm text-slate-500">输入注册邮箱获取重置链接</p></div>
        </div>
        {message && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
        {error && <div role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">邮箱</span>
          <input type="email" required autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3.5 py-3 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
        </label>
        <button type="submit" disabled={submitting} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{submitting && <Loader2 className="h-4 w-4 animate-spin" />}发送重置邮件</button>
        <p className="mt-5 text-center text-sm"><Link to="/login" className="font-medium text-primary-600">返回登录</Link></p>
      </form>
    </div>
  );
}
