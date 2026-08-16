import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, Loader2 } from 'lucide-react';
import { historyApi } from '../api/history';
import { interviewApi } from '../api/interview';
import Interview from './InterviewPage';
import { resolveKnowledgeBaseInterviewCompletion } from './knowledgeBaseInterviewCompletion';

interface SessionLocationState {
  knowledgeBaseId?: number;
}

export default function KnowledgeBaseInterviewSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const stateKbId = (location.state as SessionLocationState | undefined)?.knowledgeBaseId;
  const [kbId, setKbId] = useState<number | undefined>(stateKbId);
  const [awaitingEvaluation, setAwaitingEvaluation] = useState(false);
  const [evaluationError, setEvaluationError] = useState('');

  useEffect(() => {
    if (stateKbId !== undefined) {
      setKbId(stateKbId);
      return;
    }
    if (!sessionId) return;
    let cancelled = false;
    interviewApi
      .getSession(sessionId)
      .then(session => {
        if (!cancelled && session.knowledgeBaseId) {
          setKbId(session.knowledgeBaseId);
        }
      })
      .catch(() => {
        // 读取失败走默认兜底，不影响面试主流程
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, stateKbId]);

  useEffect(() => {
    if (!awaitingEvaluation || !sessionId || kbId === undefined) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const pollEvaluation = async () => {
      try {
        const detail = await historyApi.getInterviewDetail(sessionId);
        if (cancelled) return;

        const completion = resolveKnowledgeBaseInterviewCompletion(
          detail.evaluateStatus,
          kbId,
          sessionId,
        );
        if (completion.kind === 'completed') {
          navigate(completion.path, { replace: true });
          return;
        }
        if (completion.kind === 'failed') {
          setEvaluationError(detail.evaluateError || '面试评估失败，请前往面试记录查看');
          return;
        }
      } catch {
        if (!cancelled) {
          setEvaluationError('暂时无法获取评估进度，系统将继续重试');
        }
      }

      if (!cancelled) {
        timer = setTimeout(pollEvaluation, 3000);
      }
    };

    void pollEvaluation();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [awaitingEvaluation, kbId, navigate, sessionId]);

  if (!sessionId) {
    return <Navigate to="/knowledgebase-interview" replace />;
  }

  const backTarget = kbId
    ? `/knowledgebase-interview/${kbId}/questions`
    : '/knowledgebase-interview';

  const historyTarget = kbId
    ? `/knowledgebase-interview/${kbId}/interviews`
    : '/interviews';

  if (awaitingEvaluation) {
    return (
      <div className="max-w-xl mx-auto min-h-[55vh] flex items-center justify-center">
        <div className="w-full rounded-2xl border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800 p-8 text-center shadow-sm">
          {evaluationError && !evaluationError.includes('继续重试') ? (
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          ) : (
            <Loader2 className="w-12 h-12 mx-auto mb-4 text-primary-500 animate-spin" />
          )}
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            {evaluationError && !evaluationError.includes('继续重试')
              ? '面试评估失败'
              : '正在生成面试评估'}
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">
            {evaluationError || '答案已全部保存，通常需要几十秒。评估完成后将自动打开本次面试结果。'}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate(historyTarget)}
              className="px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              查看面试记录
            </button>
            <button
              type="button"
              onClick={() => navigate(backTarget)}
              className="px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600"
            >
              返回题库
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Interview
      resumeText=""
      sessionIdToResume={sessionId}
      title="知识库面试"
      subtitle="从已启用题库抽题，按题目评分规则评估"
      loadingText="正在加载知识库面试..."
      onBack={() => navigate(backTarget)}
      onInterviewComplete={() => setAwaitingEvaluation(true)}
    />
  );
}
