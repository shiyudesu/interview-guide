import { expect, test } from '@playwright/test';

test.describe('模拟面试加载状态', () => {
  test('生成首道题期间立即显示等待提示和加载动画', async ({ page }) => {
    await page.route('**/api/auth/config', route => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ authEnabled: false, registrationEnabled: false }),
    }));

    let releaseSession: (() => void) | undefined;
    const sessionPending = new Promise<void>(resolve => {
      releaseSession = resolve;
    });
    const session = {
      sessionId: 'session-loading-contract',
      channel: 'TEXT',
      status: 'IN_PROGRESS',
      currentQuestion: {
        questionId: 'question-1',
        kind: 'MAIN',
        parentQuestionId: null,
        question: '请介绍一个你负责过的项目。',
        type: 'PROJECT',
        category: '项目经历',
      },
      turns: [],
      progress: {
        completedMainQuestions: 0,
        plannedMainQuestions: 8,
        followUpsUsedForCurrentMain: 0,
        maxFollowUpsPerMain: 2,
      },
      knowledgeBaseId: null,
      interviewCategory: null,
    };

    await page.route('**/api/interview/sessions**', async route => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;
      if (request.method() === 'POST' && pathname === '/api/interview/sessions') {
        await sessionPending;
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(session) });
        return;
      }
      if (request.method() === 'GET' && pathname === `/api/interview/sessions/${session.sessionId}`) {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(session) });
        return;
      }
      await route.fallback();
    });

    try {
      await page.goto('/interview/create/loading-contract');

      const loadingState = page.getByRole('status').filter({ hasText: '正在生成面试题目...' });
      await expect(loadingState).toBeVisible();
      await expect(loadingState.locator('.animate-spin')).toBeVisible();
    } finally {
      releaseSession?.();
    }

    await expect(page.getByText('请介绍一个你负责过的项目。')).toBeVisible();
  });
});
