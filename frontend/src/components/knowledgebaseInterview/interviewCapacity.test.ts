import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getFollowUpQualityWarning,
  getSelectedCapacity,
  getStrictCapacityMessage,
} from './interviewCapacity.ts';

const options = [
  { followUpCount: 0, availableQuestionCount: 10, selectable: true },
  { followUpCount: 1, availableQuestionCount: 8, selectable: true },
  { followUpCount: 2, availableQuestionCount: 5, selectable: true },
  { followUpCount: 3, availableQuestionCount: 2, selectable: false },
];

test('根据动态追问上限找到后端容量选项', () => {
  assert.deepEqual(getSelectedCapacity(options, 3), options[3]);
  assert.equal(getSelectedCapacity(options, 4), null);
});

test('容量不足只按主问题数量提示', () => {
  assert.equal(
    getStrictCapacityMessage(options, 3, 5),
    '当前仅有 2 道可用主问题，无法抽取 5 道，请减少主问题数或补充题库。'
  );
});

test('所有动态追问上限都复用同一主问题容量', () => {
  const insufficientOptions = options.map(option => ({
    ...option,
    availableQuestionCount: Math.min(option.availableQuestionCount, 2),
    selectable: false,
  }));

  assert.equal(
    getStrictCapacityMessage(insufficientOptions, 3, 5),
    '当前仅有 2 道可用主问题，无法抽取 5 道，请减少主问题数或补充题库。'
  );
});

test('最近生成目标只对追问不足的题目显示质量警告', () => {
  assert.equal(getFollowUpQualityWarning(1, 2), '追问不足：实际 1 / 目标 2');
  assert.equal(getFollowUpQualityWarning(2, 2), null);
  assert.equal(getFollowUpQualityWarning(3, 2), null);
  assert.equal(getFollowUpQualityWarning(0, null), null);
});
