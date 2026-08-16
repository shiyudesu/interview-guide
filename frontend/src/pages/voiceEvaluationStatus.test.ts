import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getVoiceEvaluationPresentation,
  shouldRefreshVoiceEvaluationPresentation,
  VOICE_EVALUATION_RETRY_AFTER_MS,
} from './voiceEvaluationStatus.ts';

const now = new Date('2026-07-27T12:10:00.000Z').getTime();

test('新进入 PENDING 时展示明确的排队状态且不立即允许重复生成', () => {
  assert.deepEqual(getVoiceEvaluationPresentation({
    status: 'PENDING',
    statusUpdatedAt: '2026-07-27T12:09:40.000Z',
    now,
  }), {
    tone: 'loading',
    label: '等待评估',
    title: '正在排队生成评估报告',
    description: '通常会在 10–30 秒内开始分析，你可以先离开此页面。',
    retryable: false,
    shouldPoll: true,
  });
});

test('PENDING 超过恢复阈值后提示延迟并允许重新生成', () => {
  assert.deepEqual(getVoiceEvaluationPresentation({
    status: 'PENDING',
    statusUpdatedAt: new Date(now - VOICE_EVALUATION_RETRY_AFTER_MS).toISOString(),
    now,
  }), {
    tone: 'warning',
    label: '评估延迟',
    title: '评估等待时间较长',
    description: '任务可能没有成功进入队列，你可以重新生成，已保存的面试记录不会丢失。',
    retryable: true,
    shouldPoll: true,
  });
});

test('PROCESSING 和 FAILED 使用不同的操作提示', () => {
  assert.equal(getVoiceEvaluationPresentation({
    status: 'PROCESSING',
    statusUpdatedAt: null,
    now,
  }).title, 'AI 正在分析本次面试');

  assert.deepEqual(getVoiceEvaluationPresentation({
    status: 'FAILED',
    statusUpdatedAt: null,
    now,
  }), {
    tone: 'error',
    label: '生成失败',
    title: '评估报告生成失败',
    description: '本次面试记录已保存，你可以重新生成评估报告。',
    retryable: true,
    shouldPoll: false,
  });
});

test('只有活动中的评估需要随轮询刷新等待时间展示', () => {
  assert.equal(shouldRefreshVoiceEvaluationPresentation('PENDING'), true);
  assert.equal(shouldRefreshVoiceEvaluationPresentation('PROCESSING'), true);
  assert.equal(shouldRefreshVoiceEvaluationPresentation('COMPLETED'), false);
  assert.equal(shouldRefreshVoiceEvaluationPresentation('FAILED'), false);
  assert.equal(shouldRefreshVoiceEvaluationPresentation(null), false);
});
