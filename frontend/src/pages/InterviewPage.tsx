import {useEffect, useRef, useState} from 'react';
import {motion} from 'framer-motion';
import {interviewApi} from '../api/interview';
import ConfirmDialog from '../components/ConfirmDialog';
import InterviewChatPanel from '../components/InterviewChatPanel';
import type {InterviewQuestion, InterviewSession} from '../types/interview';
import type { Difficulty } from '../hooks/useInterviewConfig';
import type {CategoryDTO} from '../api/skill';
import { CUSTOM_SKILL_ID } from '../hooks/useInterviewConfig';
import {resolveInterviewEntry} from './interviewEntry';

interface Message {
  type: 'interviewer' | 'user';
  content: string;
  category?: string | null;
  questionId?: string;
}

interface InterviewProps {
  resumeText: string;
  resumeId?: number;
  sessionIdToResume?: string;
  requestId?: string;
  initialConfig?: {
    questionCount?: number;
    llmProvider?: string;
    skillId?: string;
    difficulty?: Difficulty;
    customCategories?: CategoryDTO[];
    jdText?: string;
  };
  title?: string;
  subtitle?: string;
  loadingText?: string;
  onBack: () => void;
  onSessionCreated?: (sessionId: string) => void;
  onInterviewComplete: () => void;
}

export default function Interview({
  resumeText,
  resumeId,
  sessionIdToResume,
  requestId,
  initialConfig,
  title = '模拟面试',
  subtitle = '认真回答每个问题，展示您的实力',
  loadingText = '正在生成面试题目...',
  onBack,
  onSessionCreated,
  onInterviewComplete,
}: InterviewProps) {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<InterviewQuestion | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [answer, setAnswer] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  // 首次渲染时请求尚未由 useEffect 发起，也必须立即展示等待状态，
  // 避免在“开始面试”与生成提示之间短暂返回空白页面。
  const [isCreating, setIsCreating] = useState(true);
  const [showCompleteConfirm, setShowCompleteConfirm] = useState(false);
  const startedRef = useRef(false);
  const pendingTurnRef = useRef<{
    questionId: string;
    answer: string;
    requestId: string;
  } | null>(null);

  const questionCount = initialConfig?.questionCount ?? 8;
  const llmProvider = initialConfig?.llmProvider ?? '';
  const skillId = initialConfig?.skillId ?? 'java-backend';
  const difficulty = initialConfig?.difficulty ?? 'mid';
  const customCategories = initialConfig?.customCategories;
  const jdText = initialConfig?.jdText;

  // 自动开始面试（恢复已有会话 或 创建新会话）
  useEffect(() => {
    if (!startedRef.current) {
      startedRef.current = true;
      const entry = resolveInterviewEntry(sessionIdToResume);
      if (entry.type === 'resume') {
        resumeExistingSession(entry.sessionId);
      } else {
        startInterview();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startInterview = async () => {
    setIsCreating(true);
    setError('');

    try {
      const newSession = await interviewApi.createSession({
        resumeText,
        questionCount,
        resumeId,
        forceCreate: true,
        llmProvider,
        skillId,
        difficulty,
        customCategories: skillId === CUSTOM_SKILL_ID ? customCategories : undefined,
        jdText: skillId === CUSTOM_SKILL_ID ? jdText : undefined,
        requestId,
      });

      initSession(newSession);
      onSessionCreated?.(newSession.sessionId);
    } catch (err) {
      setError('创建面试失败，请重试');
      console.error(err);
    } finally {
      setIsCreating(false);
    }
  };

  const resumeExistingSession = async (sessionId: string) => {
    setIsCreating(true);
    setError('');

    try {
      const existingSession = await interviewApi.getSession(sessionId);
      initSession(existingSession);

    } catch (err) {
      setError('恢复面试失败，请重试');
      console.error(err);
    } finally {
      setIsCreating(false);
    }
  };

  const initSession = (s: InterviewSession) => {
    setSession(s);
    setCurrentQuestion(s.currentQuestion);
    const restoredMessages: Message[] = [];
    s.turns.forEach(turn => {
      restoredMessages.push({
        type: 'interviewer',
        content: turn.question.question,
        category: turn.question.category,
        questionId: turn.questionId,
      });
      if (turn.answer) {
        restoredMessages.push({type: 'user', content: turn.answer});
      }
      if (turn.acknowledgement) {
        restoredMessages.push({type: 'interviewer', content: turn.acknowledgement});
      }
    });
    if (
      s.currentQuestion &&
      !s.turns.some(turn => turn.questionId === s.currentQuestion?.questionId)
    ) {
      restoredMessages.push({
        type: 'interviewer',
        content: s.currentQuestion.question,
        category: s.currentQuestion.category,
        questionId: s.currentQuestion.questionId,
      });
    }
    setMessages(restoredMessages);
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !session || !currentQuestion) return;

    setIsSubmitting(true);

    const submittedAnswer = answer.trim();
    const pending = pendingTurnRef.current;
    const turnRequest =
      pending &&
      pending.questionId === currentQuestion.questionId &&
      pending.answer === submittedAnswer
        ? pending
        : {
            questionId: currentQuestion.questionId,
            answer: submittedAnswer,
            requestId: crypto.randomUUID(),
          };
    pendingTurnRef.current = turnRequest;
    setMessages(prev => {
      const last = prev[prev.length - 1];
      return last?.type === 'user' && last.content === submittedAnswer
        ? prev
        : [...prev, {type: 'user', content: submittedAnswer}];
    });

    try {
      const response = await interviewApi.submitTurn({
        sessionId: session.sessionId,
        requestId: turnRequest.requestId,
        questionId: turnRequest.questionId,
        answer: turnRequest.answer,
      });

      pendingTurnRef.current = null;
      setAnswer('');
      setSession(prev => prev ? {
        ...prev,
        currentQuestion: response.nextQuestion,
        progress: response.progress,
        status: response.completed ? 'COMPLETED' : 'IN_PROGRESS',
      } : prev);
      if (response.acknowledgement) {
        setMessages(prev => [...prev, {
          type: 'interviewer',
          content: response.acknowledgement,
        }]);
      }
      if (response.nextQuestion) {
        const nextQuestion = response.nextQuestion;
        setCurrentQuestion(nextQuestion);
        setMessages(prev => [...prev, {
          type: 'interviewer',
          content: nextQuestion.question,
          category: nextQuestion.category,
          questionId: nextQuestion.questionId,
        }]);
      } else {
        onInterviewComplete();
      }
    } catch (err) {
      setError('提交答案失败，请重试');
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompleteEarly = async () => {
    if (!session) return;

    setIsSubmitting(true);
    try {
      await interviewApi.completeInterview(session.sessionId);
      setShowCompleteConfirm(false);
      onInterviewComplete();
    } catch (err) {
      setError('提前交卷失败，请重试');
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 加载中
  if (isCreating) {
    return (
      <div
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="flex min-h-[50vh] items-center justify-center"
      >
        <div className="w-full max-w-md rounded-2xl border border-slate-100 bg-white px-8 py-10 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="mx-auto mb-5 h-11 w-11 animate-spin rounded-full border-3 border-slate-200 border-t-primary-500 dark:border-slate-700 dark:border-t-primary-400" />
          <p className="font-medium text-slate-700 dark:text-slate-200">{loadingText}</p>
          <p className="mt-2 text-sm text-slate-400 dark:text-slate-500">AI 正在准备本次面试，请耐心等待</p>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error && !session) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <p className="text-red-500 dark:text-red-400 mb-4">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => {
                // 重试应按入口类型走对应路径：恢复失败必须重试恢复，
                // 否则会用 resumeText="" 创建一个新的默认 java-backend 普通面试，
                // 知识库面试场景下会让用户从错误页面突然跳进无关会话
                const entry = resolveInterviewEntry(sessionIdToResume);
                if (entry.type === 'resume') {
                  resumeExistingSession(entry.sessionId);
                } else {
                  startInterview();
                }
              }}
              className="px-5 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              重试
            </button>
            <button
              onClick={onBack}
              className="px-5 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600"
            >
              返回
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!session || !currentQuestion) return null;

  return (
    <div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <InterviewChatPanel
          title={title}
          subtitle={subtitle}
          session={session}
          currentQuestion={currentQuestion}
          messages={messages}
          answer={answer}
          onAnswerChange={setAnswer}
          onSubmit={handleSubmitAnswer}
          isSubmitting={isSubmitting}
          error={error}
          onShowCompleteConfirm={setShowCompleteConfirm}
        />
      </motion.div>

      {/* 提前交卷确认对话框 */}
      <ConfirmDialog
        open={showCompleteConfirm}
        title="提前交卷"
        message="确定要提前交卷吗？未回答的问题将按0分计算。"
        confirmText="确定交卷"
        cancelText="取消"
        confirmVariant="warning"
        loading={isSubmitting}
        onConfirm={handleCompleteEarly}
        onCancel={() => setShowCompleteConfirm(false)}
      />
    </div>
  );
}
