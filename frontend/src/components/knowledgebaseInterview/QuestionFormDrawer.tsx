import { FormEvent } from 'react';
import { FileText, Loader2, X } from 'lucide-react';
import type {
  KnowledgeBaseQuestion,
  KnowledgeBaseQuestionFollowUp,
  SaveKnowledgeBaseQuestionRequest,
  KnowledgeBaseQuestionStatus,
} from '../../api/knowledgebase';
import {
  INPUT_CLASS,
  STATUS_OPTIONS,
  DIFFICULTY_OPTIONS,
} from '../../constants/knowledgebaseInterview';

export interface QuestionFormState {
  difficulty: string;
  type: string;
  category: string;
  question: string;
  topicSummary: string;
  referenceAnswer: string;
  keyPoints: string;
  scoringRubric: string;
  followUps: string;
  sourceContext: string;
  status: KnowledgeBaseQuestionStatus;
}

export function emptyQuestionForm(
  defaults?: Partial<Pick<QuestionFormState, 'difficulty' | 'category'>>
): QuestionFormState {
  return {
    difficulty: defaults?.difficulty || 'mid',
    type: 'KNOWLEDGE_BASE',
    category: defaults?.category || '',
    question: '',
    topicSummary: '',
    referenceAnswer: '',
    keyPoints: '',
    scoringRubric: '',
    followUps: '',
    sourceContext: '',
    status: 'DRAFT',
  };
}

function linesToArray(value: string): string[] {
  return value.split('\n').map(item => item.trim()).filter(Boolean);
}

function arrayToLines(values?: string[]): string {
  return (values ?? []).join('\n');
}

function followUpsToText(followUps: KnowledgeBaseQuestionFollowUp[]): string {
  return followUps
    .map(item => [
      item.question,
      item.referenceAnswer || '',
      (item.keyPoints || []).join(','),
      item.scoringRubric || '',
    ].join(' | '))
    .join('\n');
}

function textToFollowUps(value: string): KnowledgeBaseQuestionFollowUp[] {
  return linesToArray(value).map(line => {
    const [question, referenceAnswer, keyPoints, scoringRubric] = line.split('|').map(item => item.trim());
    return {
      question,
      referenceAnswer: referenceAnswer || null,
      keyPoints: keyPoints ? keyPoints.split(',').map(item => item.trim()).filter(Boolean) : [],
      scoringRubric: scoringRubric || null,
    };
  });
}

export function formFromQuestion(question: KnowledgeBaseQuestion): QuestionFormState {
  return {
    difficulty: question.difficulty,
    type: question.type || '',
    category: question.category || '',
    question: question.question,
    topicSummary: question.topicSummary || '',
    referenceAnswer: question.referenceAnswer || '',
    keyPoints: arrayToLines(question.keyPoints),
    scoringRubric: question.scoringRubric || '',
    followUps: followUpsToText(question.followUps),
    sourceContext: question.sourceContext || '',
    status: question.status,
  };
}

export function buildQuestionPayload(form: QuestionFormState): SaveKnowledgeBaseQuestionRequest {
  return {
    difficulty: form.difficulty,
    type: form.type.trim() || null,
    category: form.category.trim(),
    question: form.question.trim(),
    topicSummary: form.topicSummary.trim() || null,
    referenceAnswer: form.referenceAnswer.trim() || null,
    keyPoints: linesToArray(form.keyPoints),
    scoringRubric: form.scoringRubric.trim() || null,
    followUps: textToFollowUps(form.followUps),
    sourceContext: form.sourceContext.trim() || null,
    status: form.status,
  };
}

interface QuestionFormDrawerProps {
  form: QuestionFormState;
  editing: boolean;
  saving: boolean;
  error: string;
  categoryOptions?: string[];
  onChange: (form: QuestionFormState) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}

export default function QuestionFormDrawer({
  form,
  editing,
  saving,
  error,
  categoryOptions = [],
  onChange,
  onClose,
  onSubmit,
}: QuestionFormDrawerProps) {
  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        className="absolute inset-y-0 left-0 bg-black/40"
        style={{ right: 'min(42rem, 100vw)' }}
        onClick={onClose}
        aria-label="关闭表单"
      />
      <form
        onSubmit={onSubmit}
        className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto bg-white dark:bg-slate-900 shadow-2xl border-l border-slate-200 dark:border-slate-700"
      >
        <div className="sticky top-0 z-10 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-700 px-5 py-4 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-slate-900 dark:text-white">{editing ? '编辑题目' : '新增题目'}</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">维护题干、答案、评分规则和追问</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="难度">
              <select value={form.difficulty} onChange={event => onChange({ ...form, difficulty: event.target.value })} className={INPUT_CLASS}>
                {DIFFICULTY_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </Field>
            <Field label="状态">
              <select value={form.status} onChange={event => onChange({ ...form, status: event.target.value as KnowledgeBaseQuestionStatus })} className={INPUT_CLASS}>
                {STATUS_OPTIONS.filter(option => option.value).map(option => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="面试方向（用于筛选和开始面试）">
            <input
              value={form.category}
              list="knowledge-base-question-category-options"
              onChange={event => onChange({ ...form, category: event.target.value })}
              className={INPUT_CLASS}
              placeholder="例如 整洁架构 / Redis / JVM 调优"
            />
            {categoryOptions.length > 0 && (
              <datalist id="knowledge-base-question-category-options">
                {categoryOptions.map(category => (
                  <option key={category} value={category} />
                ))}
              </datalist>
            )}
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              可输入新方向，或从已有方向中选择。
            </p>
          </Field>
          <Field label="题干">
            <textarea value={form.question} onChange={event => onChange({ ...form, question: event.target.value })} className={`${INPUT_CLASS} min-h-24 resize-y`} />
          </Field>
          <Field label="参考答案">
            <textarea value={form.referenceAnswer} onChange={event => onChange({ ...form, referenceAnswer: event.target.value })} className={`${INPUT_CLASS} min-h-28 resize-y`} />
          </Field>
          <Field label="评分要点（每行一条）">
            <textarea value={form.keyPoints} onChange={event => onChange({ ...form, keyPoints: event.target.value })} className={`${INPUT_CLASS} min-h-20 resize-y`} />
          </Field>
          <Field label="评分规则">
            <textarea value={form.scoringRubric} onChange={event => onChange({ ...form, scoringRubric: event.target.value })} className={`${INPUT_CLASS} min-h-20 resize-y`} />
          </Field>
          <Field label="追问（每行：题干 | 参考答案 | 要点1,要点2 | 评分规则）">
            <textarea value={form.followUps} onChange={event => onChange({ ...form, followUps: event.target.value })} className={`${INPUT_CLASS} min-h-24 resize-y`} />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        <div className="sticky bottom-0 bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-700 px-5 py-4 flex items-center justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">
            取消
          </button>
          <button type="submit" disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white font-medium hover:bg-primary-600 disabled:opacity-50">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            保存
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">{label}</span>
      {children}
    </label>
  );
}
