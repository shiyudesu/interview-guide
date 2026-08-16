import assert from 'node:assert/strict';
import test from 'node:test';

import {resolveInterviewEntry} from './interviewEntry.ts';
import {ROUTE_PATTERNS, ROUTES} from '../constants/routes.ts';

test('恢复入口重试时仍使用原会话 ID', () => {
  assert.deepEqual(resolveInterviewEntry('session-42'), {
    type: 'resume',
    sessionId: 'session-42',
  });
});

test('新建入口没有会话 ID 时创建新会话', () => {
  assert.deepEqual(resolveInterviewEntry(undefined), {type: 'create'});
});

test('文本面试动态路由由统一常量构造', () => {
  assert.equal(ROUTES.interviewCreate('request-1'), '/interview/create/request-1');
  assert.equal(ROUTES.interviewSession('session-1'), '/interview/session/session-1');
  assert.equal(ROUTE_PATTERNS.interviewCreate, 'interview/create/:requestId');
  assert.equal(ROUTE_PATTERNS.interviewSession, 'interview/session/:activeSessionId');
});
