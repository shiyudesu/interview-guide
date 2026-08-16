export type InterviewEntry =
  | {type: 'create'}
  | {type: 'resume'; sessionId: string};

export function resolveInterviewEntry(sessionIdToResume?: string): InterviewEntry {
  return sessionIdToResume
    ? {type: 'resume', sessionId: sessionIdToResume}
    : {type: 'create'};
}
