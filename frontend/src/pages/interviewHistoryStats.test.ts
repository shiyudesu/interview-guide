import assert from 'node:assert/strict';
import test from 'node:test';

import {
  calculateInterviewStats,
  getKnowledgeBaseInterviewCategoryLabel,
} from './interviewHistoryStats.ts';

const allItems = [
  { status: 'IN_PROGRESS', evaluateStatus: null, overallScore: null },
  { status: 'COMPLETED', evaluateStatus: 'PROCESSING', overallScore: null },
  { status: 'EVALUATED', evaluateStatus: 'COMPLETED', overallScore: 80 },
];

test('普通面试页保持按全部记录统计，不受当前筛选结果影响', () => {
  const stats = calculateInterviewStats(allItems, [allItems[2]], false);

  assert.deepEqual(stats, {
    totalCount: 3,
    completedCount: 1,
    averageScore: 80,
  });
});

test('知识库面试页按筛选结果统计，评估中的记录不计为已完成', () => {
  const filteredItems = [allItems[1], allItems[2]];

  const stats = calculateInterviewStats(allItems, filteredItems, true);

  assert.deepEqual(stats, {
    totalCount: 2,
    completedCount: 1,
    averageScore: 80,
  });
});

test('没有限定方向的知识库面试显示为全部方向', () => {
  assert.equal(getKnowledgeBaseInterviewCategoryLabel(null), '全部方向');
  assert.equal(getKnowledgeBaseInterviewCategoryLabel(''), '全部方向');
  assert.equal(getKnowledgeBaseInterviewCategoryLabel('操作系统'), '操作系统');
});
