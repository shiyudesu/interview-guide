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

  test('聊天工作区占满可用高度，并将输入区固定在底部', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.route('**/api/auth/config', route => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ authEnabled: false, registrationEnabled: false }),
    }));

    const sessionId = 'session-chat-layout';
    const currentQuestion = {
      questionId: 'question-4',
      kind: 'MAIN',
      parentQuestionId: null,
      question: '如果线上服务突然出现延迟升高，你会如何定位问题？',
      type: 'TECH',
      category: '系统设计',
    };
    const session = {
      sessionId,
      channel: 'TEXT',
      status: 'IN_PROGRESS',
      currentQuestion,
      turns: Array.from({ length: 3 }, (_, index) => ({
        turnId: `turn-${index + 1}`,
        questionId: `question-${index + 1}`,
        question: {
          ...currentQuestion,
          questionId: `question-${index + 1}`,
          question: `请说明第 ${index + 1} 个项目场景中的技术取舍。`,
        },
        answer: `这是第 ${index + 1} 个回答。我会先明确业务目标，再从一致性、可用性和维护成本三个方面比较方案。`,
        action: 'NEXT_MAIN',
        acknowledgement: '好的，我们继续看下一个场景。',
        nextQuestionId: `question-${index + 2}`,
        decisionStatus: 'COMPLETED',
        answeredAt: '2026-08-26T00:00:00Z',
        decidedAt: '2026-08-26T00:00:01Z',
      })),
      progress: {
        completedMainQuestions: 3,
        plannedMainQuestions: 8,
        followUpsUsedForCurrentMain: 0,
        maxFollowUpsPerMain: 2,
      },
      knowledgeBaseId: null,
      interviewCategory: null,
    };

    await page.route(`**/api/interview/sessions/${sessionId}`, route => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(session),
    }));

    await page.goto(`/interview/session/${sessionId}`);

    const workspace = page.getByTestId('interview-workspace');
    const messageList = page.getByTestId('interview-message-list');
    const composer = page.getByTestId('interview-composer');
    await expect(workspace).toBeVisible();
    await expect(composer).toBeVisible();

    const [workspaceBox, messageListBox, composerBox] = await Promise.all([
      workspace.boundingBox(),
      messageList.boundingBox(),
      composer.boundingBox(),
    ]);
    expect(workspaceBox).not.toBeNull();
    expect(messageListBox).not.toBeNull();
    expect(composerBox).not.toBeNull();
    expect(workspaceBox!.height).toBeGreaterThan(780);
    expect(messageListBox!.height).toBeGreaterThan(430);
    expect(composerBox!.y + composerBox!.height).toBeLessThanOrEqual(workspaceBox!.y + workspaceBox!.height);

    const answerInput = page.getByPlaceholder('输入你的回答...');
    const initialHeight = await answerInput.evaluate(element => element.getBoundingClientRect().height);
    await answerInput.fill(Array.from({ length: 10 }, (_, index) => `第 ${index + 1} 行回答`).join('\n'));
    const expandedHeight = await answerInput.evaluate(element => element.getBoundingClientRect().height);
    expect(expandedHeight).toBeGreaterThan(initialHeight);
    expect(expandedHeight).toBeLessThanOrEqual(200);
  });
});
