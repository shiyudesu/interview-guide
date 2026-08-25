import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, Loader2, LogOut, ShieldCheck, UserRound } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { getErrorMessage } from '../api/request';

export default function AccountPage() {
  const { user, authenticationEnabled, changePassword, revokeSessions } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [error, setError] = useState('');

  const submitPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await changePassword({ currentPassword, newPassword });
      navigate('/login', { replace: true, state: { message: '密码已修改，请重新登录' } });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const revokeAll = async () => {
    if (!window.confirm('确定撤销该账号的全部登录 Session 吗？当前设备也会退出。')) return;
    setRevoking(true);
    setError('');
    try {
      await revokeSessions();
      navigate('/login', { replace: true, state: { message: '全部 Session 已撤销，请重新登录' } });
    } catch (caught) {
      setError(getErrorMessage(caught));
      setRevoking(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex items-center gap-4">
        <div className="rounded-xl bg-primary-500 p-3 text-white shadow-lg shadow-primary-500/25"><UserRound className="h-6 w-6" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-white">账号与安全</h1>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">管理密码和已登录设备</p>
        </div>
      </div>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-emerald-500" />
          <div>
            <p className="font-semibold text-slate-800 dark:text-white">{user?.displayName || user?.email}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">{user?.email} · {user?.role}</p>
          </div>
        </div>
      </section>

      {!authenticationEnabled ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
          当前是临时单用户验收模式，账号与 Session 功能未启用。正式公网部署请使用 HTTPS 并启用认证。
        </div>
      ) : (
        <>
          {error && <div role="alert" className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          <form onSubmit={submitPassword} className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-5 flex items-center gap-2"><KeyRound className="h-5 w-5 text-primary-500" /><h2 className="font-semibold text-slate-800 dark:text-white">修改密码</h2></div>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="block"><span className="mb-1.5 block text-sm text-slate-600 dark:text-slate-300">当前密码</span><input type="password" required autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></label>
              <label className="block"><span className="mb-1.5 block text-sm text-slate-600 dark:text-slate-300">新密码</span><input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></label>
              <label className="block"><span className="mb-1.5 block text-sm text-slate-600 dark:text-slate-300">确认新密码</span><input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></label>
            </div>
            <button type="submit" disabled={saving} className="mt-5 flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50">{saving && <Loader2 className="h-4 w-4 animate-spin" />}修改密码并退出</button>
          </form>

          <section className="rounded-2xl border border-red-200 bg-white p-6 shadow-sm dark:border-red-900/60 dark:bg-slate-800">
            <div className="flex items-start justify-between gap-5">
              <div><div className="flex items-center gap-2"><LogOut className="h-5 w-5 text-red-500" /><h2 className="font-semibold text-slate-800 dark:text-white">撤销全部 Session</h2></div><p className="mt-2 text-sm text-slate-500 dark:text-slate-400">使所有设备上的登录立即失效，适用于怀疑账号泄露时。</p></div>
              <button type="button" onClick={revokeAll} disabled={revoking} className="flex shrink-0 items-center gap-2 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300">{revoking && <Loader2 className="h-4 w-4 animate-spin" />}全部退出</button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
