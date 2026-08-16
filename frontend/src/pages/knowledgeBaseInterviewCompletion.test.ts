import assert from 'node:assert/strict';
import test from 'node:test';

import {
  resolveKnowledgeBaseInterviewCompletion,
} from './knowledgeBaseInterviewCompletion.ts';

test('评估排队或处理中时停留在等待页', () => {
  assert.deepEqual(
    resolveKnowledgeBaseInterviewCompletion('PENDING', 1, 'session-1'),
    { kind: 'waiting' },
  );
  assert.deepEqual(
    resolveKnowledgeBaseInterviewCompletion('PROCESSING', 1, 'session-1'),
    { kind: 'waiting' },
  );
});

test('评估完成后进入本次知识库面试详情', () => {
  assert.deepEqual(
    resolveKnowledgeBaseInterviewCompletion('COMPLETED', 1, 'session-1'),
    {
      kind: 'completed',
      path: '/knowledgebase-interview/1/interviews/session-1',
    },
  );
});

test('评估失败后停留在等待页并显示失败状态', () => {
  assert.deepEqual(
    resolveKnowledgeBaseInterviewCompletion('FAILED', 1, 'session-1'),
    { kind: 'failed' },
  );
});
