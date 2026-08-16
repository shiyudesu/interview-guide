import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getQuestionGenerationNotice,
  isQuestionGenerationActive,
  shouldRefreshGeneratedQuestions,
} from './questionGenerationStatus.ts';

test('QUEUED 和 PROCESSING 都属于活动生成状态', () => {
  assert.equal(isQuestionGenerationActive('QUEUED'), true);
  assert.equal(isQuestionGenerationActive('PROCESSING'), true);
  assert.equal(isQuestionGenerationActive('COMPLETED'), false);
  assert.equal(isQuestionGenerationActive('FAILED'), false);
});

test('只有正在跟踪的活动任务进入 COMPLETED 时刷新题目', () => {
  assert.equal(shouldRefreshGeneratedQuestions('PROCESSING', 'COMPLETED', true), true);
  assert.equal(shouldRefreshGeneratedQuestions('QUEUED', 'COMPLETED', true), true);
  assert.equal(shouldRefreshGeneratedQuestions('COMPLETED', 'COMPLETED', true), false);
  assert.equal(shouldRefreshGeneratedQuestions('PROCESSING', 'COMPLETED', false), false);
  assert.equal(shouldRefreshGeneratedQuestions(null, 'COMPLETED', true), false);
});

test('状态提示不暴露后端异常细节', () => {
  assert.deepEqual(getQuestionGenerationNotice({
    questionGenStatus: 'FAILED',
    message: null,
    error: '数据库连接 jdbc:postgresql://internal-host 失败',
    savedCount: 0,
    skippedCount: 0,
  }), {
    tone: 'error',
    text: '题目生成失败，请稍后重试',
  });
});
