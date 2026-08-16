import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowDownUp,
  BookOpen,
  Database,
  Loader2,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react';
import {
  knowledgeBaseApi,
  type KnowledgeBaseItem,
} from '../api/knowledgebase';
import { DEFAULT_DIFFICULTY, DEFAULT_CATEGORY_LIMIT, INPUT_CLASS } from '../constants/knowledgebaseInterview';
import StartKnowledgeBaseInterviewModal, {
  type StartInterviewConfig,
} from '../components/knowledgebaseInterview/StartKnowledgeBaseInterviewModal';
import GenerateKnowledgeBaseQuestionsModal, {
  type GenerateQuestionsConfig,
} from '../components/knowledgebaseInterview/GenerateKnowledgeBaseQuestionsModal';
import KnowledgeBaseCard from '../components/knowledgebaseInterview/KnowledgeBaseCard';
import { isQuestionGenerationActive } from './questionGenerationStatus';

type SortKey = 'time' | 'name' | 'question';

const SORT_OPTIONS: Array<{ value: SortKey; label: string }> = [
  { value: 'time', label: '按时间' },
  { value: 'name', label: '按名称' },
  { value: 'question', label: '按题目数' },
];

export default function KnowledgeBaseInterviewLandingPage() {
  const navigate = useNavigate();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('time');

  const [startTarget, setStartTarget] = useState<KnowledgeBaseItem | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  const [generateTarget, setGenerateTarget] = useState<KnowledgeBaseItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [generateError, setGenerateError] = useState('');

  const loadKnowledgeBases = useCallback(async () => {
    setLoading(true);
    try {
      const list = await knowledgeBaseApi.getAllKnowledgeBases(sortKey === 'question' ? 'question' : 'time', 'COMPLETED');
      setKnowledgeBases(list);
    } finally {
      setLoading(false);
    }
  }, [sortKey]);

  useEffect(() => {
    loadKnowledgeBases();
  }, [loadKnowledgeBases]);

  const hasActiveGeneration = knowledgeBases.some(kb =>
    isQuestionGenerationActive(kb.questionGenStatus)
  );

  useEffect(() => {
    if (!hasActiveGeneration) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const list = await knowledgeBaseApi.getAllKnowledgeBases(
          sortKey === 'question' ? 'question' : 'time',
          'COMPLETED'
        );
        if (!cancelled) setKnowledgeBases(list);
      } finally {
        if (!cancelled) timer = setTimeout(poll, 5000);
      }
    };

    timer = setTimeout(poll, 5000);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [hasActiveGeneration, sortKey]);

  const filteredAndSorted = useMemo(() => {
    const trimmed = keyword.trim().toLowerCase();
    const list = trimmed
      ? knowledgeBases.filter(kb =>
          kb.name.toLowerCase().includes(trimmed)
          || (kb.originalFilename || '').toLowerCase().includes(trimmed)
        )
      : [...knowledgeBases];

    switch (sortKey) {
      case 'name':
        list.sort((a, b) => a.name.localeCompare(b.name, 'zh'));
        break;
      case 'question':
        list.sort((a, b) => b.questionCount - a.questionCount);
        break;
      case 'time':
      default:
        list.sort((a, b) => (b.uploadedAt || '').localeCompare(a.uploadedAt || ''));
        break;
    }
    return list;
  }, [knowledgeBases, keyword, sortKey]);

  const handleStart = (kb: KnowledgeBaseItem) => {
    setStartTarget(kb);
    setStartError('');
  };

  const handleGenerate = (kb: KnowledgeBaseItem) => {
    if (isQuestionGenerationActive(kb.questionGenStatus)) return;
    setGenerateTarget(kb);
    setGenerateError('');
  };

  const handleManage = (kb: KnowledgeBaseItem) => {
    navigate(`/knowledgebase-interview/${kb.id}/questions`);
  };

  const handleStartSubmit = async (config: StartInterviewConfig) => {
    if (!startTarget) return;
    setStarting(true);
    setStartError('');
    try {
      const session = await knowledgeBaseApi.createInterviewSession({
        knowledgeBaseId: startTarget.id,
        category: config.category.trim() || undefined,
        difficulty: config.difficulty,
        mainQuestionCount: config.mainQuestionCount,
        followUpCount: config.followUpCount,
      });
      const kbId = startTarget.id;
      setStartTarget(null);
      navigate(`/knowledgebase-interview/${session.sessionId}`, {
        state: { knowledgeBaseId: kbId },
      });
    } catch (error) {
      setStartError(error instanceof Error ? error.message : '创建知识库面试失败');
    } finally {
      setStarting(false);
    }
  };

  const handleGenerateSubmit = async (config: GenerateQuestionsConfig) => {
    if (!generateTarget) return;
    setSubmitting(true);
    setGenerateError('');
    try {
      const result = await knowledgeBaseApi.generateQuestions(generateTarget.id, {
        difficulty: config.difficulty,
        questionCount: config.questionCount,
        followUpCount: config.followUpCount,
        categoryLimit: config.categoryLimit,
      });
      setGenerateTarget(null);
      navigate(`/knowledgebase-interview/${generateTarget.id}/questions`, {
        state: {
          highlightStatus: 'DRAFT',
          questionGenTaskId: result.questionGenTaskId,
        },
      });
    } catch (error) {
      setGenerateError(error instanceof Error ? error.message : '生成失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <BookOpen className="w-7 h-7 text-primary-500" />
            知识库面试
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            选择知识库进入面试，或维护题库
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadKnowledgeBases}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 whitespace-nowrap"
          >
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
          <button
            onClick={() => navigate('/knowledgebase/upload')}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 whitespace-nowrap"
          >
            <Plus className="w-4 h-4" />
            上传知识库
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl p-3 mb-6 flex flex-col sm:flex-row gap-3 sm:items-center">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={keyword}
            onChange={event => setKeyword(event.target.value)}
            className={`${INPUT_CLASS} pl-9`}
            placeholder="按名称或文件名搜索"
          />
        </div>
        <div className="flex items-center gap-2">
          <ArrowDownUp className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            value={sortKey}
            onChange={event => setSortKey(event.target.value as SortKey)}
            className={`${INPUT_CLASS} sm:w-40`}
          >
            {SORT_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
        </div>
      ) : filteredAndSorted.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[320px] rounded-2xl border border-dashed border-slate-200 dark:border-slate-700 text-slate-400 gap-3">
          <Database className="w-10 h-10" />
          <p className="text-sm">
            {keyword.trim() ? '没有匹配的知识库' : '暂无已完成知识库，先上传并等待向量化完成'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredAndSorted.map(kb => (
            <KnowledgeBaseCard
              key={kb.id}
              kb={kb}
              onStart={handleStart}
              onGenerate={handleGenerate}
              onManage={handleManage}
            />
          ))}
        </div>
      )}

      <StartKnowledgeBaseInterviewModal
        open={startTarget !== null}
        knowledgeBase={startTarget}
        defaultDifficulty={DEFAULT_DIFFICULTY}
        starting={starting}
        error={startError}
        onClose={() => {
          if (!starting) {
            setStartTarget(null);
            setStartError('');
          }
        }}
        onStart={handleStartSubmit}
      />

      <GenerateKnowledgeBaseQuestionsModal
        open={generateTarget !== null}
        knowledgeBaseName={generateTarget?.name || ''}
        defaultDifficulty={DEFAULT_DIFFICULTY}
        defaultCategoryLimit={DEFAULT_CATEGORY_LIMIT}
        submitting={submitting}
        error={generateError}
        onClose={() => {
          if (!submitting) {
            setGenerateTarget(null);
            setGenerateError('');
          }
        }}
        onSubmit={handleGenerateSubmit}
      />
    </div>
  );
}
