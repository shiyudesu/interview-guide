import { useEffect, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Loader2, MailCheck, XCircle } from 'lucide-react';
import { authApi } from '../api/auth';
import { getErrorMessage } from '../api/request';

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [state, setState] = useState<'loading' | 'success' | 'error'>(token ? 'loading' : 'error');
  const [message, setMessage] = useState(token ? '正在验证邮箱…' : '验证链接缺少 Token');

  useEffect(() => {
    if (!token) return;
    let active = true;
    authApi.confirmEmailVerification(token)
      .then(() => {
        if (active) {
          setState('success');
          setMessage('邮箱验证成功，现在可以登录了。');
        }
      })
      .catch(error => {
        if (active) {
          setState('error');
          setMessage(getErrorMessage(error));
        }
      });
    return () => { active = false; };
  }, [token]);

  const icon = state === 'loading'
    ? <Loader2 className="h-7 w-7 animate-spin" />
    : state === 'success'
      ? <CheckCircle2 className="h-7 w-7" />
      : <XCircle className="h-7 w-7" />;

  return <AuthActionCard icon={icon} title="邮箱验证" message={message} success={state === 'success'} />;
}

function AuthActionCard({ icon, title, message, success }: { icon: ReactNode; title: string; message: string; success: boolean }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-2xl dark:bg-slate-900">
        <div className={`mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl ${success ? 'bg-emerald-100 text-emerald-600' : 'bg-primary-100 text-primary-600'}`}>{icon}</div>
        <MailCheck className="mx-auto mb-2 h-5 w-5 text-slate-400" />
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h1>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{message}</p>
        <Link to="/login" className="mt-6 inline-flex rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700">返回登录</Link>
      </div>
    </div>
  );
}
