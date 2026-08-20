import type { CategoryDTO } from '../api/skill';

export type InterviewChannel = 'TEXT' | 'KNOWLEDGE_BASE' | 'VOICE';
export type InterviewStatus = 'CREATED' | 'IN_PROGRESS' | 'COMPLETED' | 'EVALUATED';
export type QuestionKind = 'MAIN' | 'FOLLOW_UP';
export type TurnAction = 'FOLLOW_UP' | 'NEXT_MAIN' | 'COMPLETE';
export type TurnDecisionStatus = 'PROCESSING' | 'COMPLETED' | 'FALLBACK' | 'FAILED';

export interface InterviewQuestion {
  questionId: string;
  kind: QuestionKind;
  parentQuestionId: string | null;
  question: string;
  type: string;
  category: string | null;
  topicSummary?: string | null;
  phase?: string | null;
}

export interface InterviewTurn {
  turnId: string;
  questionId: string;
  question: InterviewQuestion;
  answer: string | null;
  action: TurnAction | null;
  acknowledgement: string | null;
  nextQuestionId: string | null;
  decisionStatus: TurnDecisionStatus;
  answeredAt: string;
  decidedAt: string | null;
}

export interface InterviewProgress {
  completedMainQuestions: number;
  plannedMainQuestions: number;
  followUpsUsedForCurrentMain: number;
  maxFollowUpsPerMain: number;
}

export interface InterviewSession {
  sessionId: string;
  channel: InterviewChannel;
  status: InterviewStatus;
  currentQuestion: InterviewQuestion | null;
  turns: InterviewTurn[];
  progress: InterviewProgress;
  knowledgeBaseId: number | null;
  interviewCategory: string | null;
}

export interface CreateInterviewRequest {
  resumeText?: string;
  questionCount: number;
  resumeId?: number;
  forceCreate?: boolean;
  llmProvider?: string;
  skillId: string;
  difficulty?: string;
  customCategories?: CategoryDTO[];
  jdText?: string;
  requestId?: string;
}

export interface SubmitTurnRequest {
  sessionId: string;
  requestId: string;
  questionId: string;
  answer: string;
}

export interface SubmitTurnResponse {
  turnId: string;
  action: TurnAction;
  acknowledgement: string;
  nextQuestion: InterviewQuestion | null;
  completed: boolean;
  progress: InterviewProgress;
}

export interface CurrentQuestionResponse {
  completed: boolean;
  question?: InterviewQuestion;
  message?: string;
}

export interface CategoryScore {
  category: string | null;
  score: number;
  questionCount: number;
}

export interface TurnEvaluation {
  questionId: string;
  question: string;
  answer: string | null;
  score: number;
  feedback: string;
  referenceAnswer: string | null;
  keyPoints: string[];
}

export interface QuestionGroupEvaluation {
  mainQuestion: TurnEvaluation;
  followUps: TurnEvaluation[];
  groupScore: number;
  groupFeedback: string;
  category: string | null;
}

export interface InterviewReport {
  sessionId: string;
  plannedMainQuestions: number;
  answeredMainQuestions: number;
  overallScore: number;
  categoryScores: CategoryScore[];
  questionGroups: QuestionGroupEvaluation[];
  overallFeedback: string;
  strengths: string[];
  improvements: string[];
}
