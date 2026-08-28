import { expect, test, type Page, type Route } from '@playwright/test';

const API_ROUTE = /^https?:\/\/[^/]+\/api\//;

const resume = {
  id: 7,
  filename: '移动端候选人简历.pdf',
  fileSize: 1024,
  uploadedAt: '2026-08-28T08:00:00',
  accessCount: 1,
  latestScore: 86,
  lastAnalyzedAt: '2026-08-28T08:10:00',
  interviewCount: 2,
  analyzeStatus: 'COMPLETED',
  analyzeError: null,
};

const knowledgeBase = {
  id: 11,
  name: '后端面试知识库',
  category: '后端',
  originalFilename: 'backend.md',
  fileSize: 2048,
  contentType: 'text/markdown',
  uploadedAt: '2026-08-28T08:00:00',
  lastAccessedAt: '2026-08-28T09:00:00',
  accessCount: 3,
  questionCount: 4,
  vectorStatus: 'COMPLETED',
  vectorError: null,
  chunkCount: 8,
  questionGenStatus: 'COMPLETED',
  questionGenError: null,
};

const provider = {
  id: 'dashscope',
  baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  maskedApiKey: 'sk-****cope',
  hasApiKey: true,
  model: 'qwen3.7-max',
  embeddingModel: 'qwen3.7-text-embedding',
  embeddingDimensions: 1024,
  supportsEmbedding: true,
  temperature: 0.2,
  defaultChatProvider: true,
  defaultEmbeddingProvider: true,
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApiRoutes(page: Page, authEnabled = false) {
  await page.route(API_ROUTE, async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === '/api/auth/config') {
      return json(route, { authEnabled, registrationEnabled: false });
    }
    if (path === '/api/auth/me') {
      return json(route, { code: 1001, detail: '登录状态无效或已过期' }, 401);
    }
    if (path === '/api/resumes') return json(route, [resume]);
    if (path === '/api/interview/skills') return json(route, []);
    if (path === '/api/interview/sessions/mobile-session') {
      return json(route, {
        sessionId: 'mobile-session',
        channel: 'TEXT',
        status: 'IN_PROGRESS',
        currentQuestion: {
          questionId: 'mobile-question',
          kind: 'MAIN',
          parentQuestionId: null,
          question: '请介绍一个你负责过的移动端友好项目。',
          type: 'PROJECT',
          category: '项目经历',
        },
        turns: [],
        progress: {
          completedMainQuestions: 0,
          plannedMainQuestions: 6,
          followUpsUsedForCurrentMain: 0,
          maxFollowUpsPerMain: 2,
        },
        knowledgeBaseId: null,
        interviewCategory: null,
      });
    }
    if (path === '/api/interview/sessions') return json(route, [{
      sessionId: 'text-mobile-1',
      skillId: 'java-backend',
      difficulty: 'MEDIUM',
      resumeId: 7,
      channel: 'TEXT',
      plannedMainQuestions: 6,
      answeredMainQuestions: 6,
      status: 'EVALUATED',
      evaluateStatus: 'COMPLETED',
      evaluateError: null,
      overallScore: 88,
      knowledgeBaseId: null,
      interviewCategory: null,
      createdAt: '2026-08-28T08:00:00',
      completedAt: '2026-08-28T08:30:00',
    }]);
    if (path === '/api/voice-interview/sessions') {
      if (route.request().method() === 'POST') {
        return json(route, {
          sessionId: 42,
          roleType: 'JAVA_BACKEND',
          currentPhase: 'TECH',
          status: 'IN_PROGRESS',
          startTime: '2026-08-28T08:00:00Z',
          plannedDuration: 15,
          webSocketUrl: 'ws://voice-mobile.test/42',
        });
      }
      return json(route, []);
    }
    if (path === '/api/interview-schedule') {
      return json(route, [{
        id: 21,
        companyName: '示例科技',
        position: '后端工程师',
        interviewTime: '2026-08-28T19:30:00',
        interviewType: 'VIDEO',
        meetingLink: 'https://meeting.example.test/21',
        roundNumber: 1,
        interviewer: '李老师',
        notes: '准备项目介绍',
        status: 'PENDING',
        createdAt: '2026-08-28T08:00:00',
        updatedAt: '2026-08-28T08:00:00',
      }]);
    }
    if (path === '/api/knowledgebase/list') return json(route, [knowledgeBase]);
    if (path === '/api/knowledgebase/categories') return json(route, ['后端']);
    if (path === '/api/knowledgebase/stats') {
      return json(route, {
        totalCount: 1,
        totalQuestionCount: 4,
        totalAccessCount: 3,
        completedCount: 1,
        processingCount: 0,
      });
    }
    if (path === '/api/rag-chat/sessions') return json(route, []);
    if (path === '/api/llm-provider/list') return json(route, [provider]);
    if (path === '/api/llm-provider/default-provider') {
      return json(route, { defaultProvider: 'dashscope', defaultEmbeddingProvider: 'dashscope' });
    }
    if (path === '/api/llm-provider/voice/asr') {
      return json(route, {
        providerId: 'dashscope',
        url: 'wss://example.test/asr',
        model: 'qwen3-asr-flash-realtime',
        maskedApiKey: 'sk-****cope',
        language: 'zh',
        format: 'pcm',
        sampleRate: 16000,
        enableTurnDetection: true,
        turnDetectionType: 'server_vad',
        turnDetectionThreshold: 0.5,
        turnDetectionSilenceDurationMs: 800,
      });
    }
    if (path === '/api/llm-provider/voice/tts') {
      return json(route, {
        providerId: 'dashscope',
        url: 'wss://example.test/tts',
        model: 'qwen3-tts-flash-realtime',
        maskedApiKey: 'sk-****cope',
        voice: 'Cherry',
        format: 'pcm',
        sampleRate: 24000,
        mode: 'server_commit',
        languageType: 'Chinese',
        speechRate: 1,
        volume: 50,
      });
    }

    return json(route, { code: 404, detail: `未配置测试路由: ${path}` }, 404);
  });
}

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => (
    document.documentElement.scrollWidth - window.innerWidth
  ));
  expect(overflow).toBeLessThanOrEqual(1);
}

test('移动导航、简历卡片和确认弹窗保持在视口内', async ({ page }) => {
  await installApiRoutes(page);
  await page.goto('/history');

  await expect(page.getByRole('heading', { name: '简历管理' })).toBeVisible();
  await expect(page.getByTestId('resume-mobile-list')).toBeVisible();
  await expect(page.locator('table')).toBeHidden();
  await expectNoDocumentOverflow(page);

  await page.getByRole('button', { name: '打开导航' }).click();
  const navigation = page.getByRole('dialog', { name: '移动导航' });
  await expect(navigation).toBeVisible();
  await navigation.getByRole('link', { name: /面试记录/ }).click();
  await expect(page).toHaveURL(/\/interviews$/);
  await expect(page.getByRole('heading', { name: '面试记录', exact: true })).toBeVisible();
  await expect(page.getByTestId('interview-mobile-list')).toBeVisible();

  await page.goto('/knowledgebase');
  await expect(page.getByTestId('knowledgebase-mobile-list')).toBeVisible();
  await expect(page.locator('table')).toBeHidden();
  await expectNoDocumentOverflow(page);

  await page.goto('/history');
  await page.getByTestId('resume-mobile-list').getByRole('button', { name: '删除' }).click();
  const dialog = page.getByRole('dialog', { name: '删除简历' });
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(360);
  await expect(dialog.getByRole('button', { name: '确定删除' })).toBeVisible();
});

test('手机日程默认列表并提供触控友好的表单', async ({ page }) => {
  await installApiRoutes(page);
  await page.goto('/interview-schedule');

  await expect(page.getByRole('heading', { name: '面试列表' })).toBeVisible();
  await expect(page.getByRole('button', { name: '周视图' })).toHaveCount(0);
  await expect(page.getByText('示例科技')).toBeVisible();
  await expectNoDocumentOverflow(page);

  await page.getByRole('button', { name: '添加面试' }).click();
  const dialog = page.getByRole('dialog', { name: '添加面试' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('粘贴面试邀约文本')).toBeVisible();
  await expect(dialog.getByRole('button', { name: '关闭' })).toBeVisible();
});

test('知识库问答在手机上使用独立辅助面板', async ({ page }) => {
  await installApiRoutes(page);
  await page.goto('/knowledgebase/chat');

  await page.getByRole('button', { name: '知识库（0）' }).click();
  const selector = page.getByRole('dialog', { name: '选择知识库' });
  await expect(selector).toBeVisible();
  await selector.getByRole('button', { name: /后端/ }).click();
  await expect(selector.getByText('后端面试知识库')).toBeVisible();
  await selector.locator('input[type="checkbox"]').check();
  await selector.getByRole('button', { name: '关闭知识库选择' }).click();
  await expect(selector).toBeHidden();
  await expect(page.getByRole('button', { name: '知识库（1）' })).toBeVisible();
  await expectNoDocumentOverflow(page);
});

test('设置长表单使用移动端近全屏弹窗', async ({ page }) => {
  await installApiRoutes(page);
  await page.goto('/settings');

  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible();
  await page.getByRole('button', { name: '新增 Provider' }).click();
  const dialog = page.getByRole('dialog', { name: '新增 Provider' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Provider ID')).toBeVisible();
  await expect(dialog.getByRole('button', { name: '关闭' })).toBeVisible();
  await expectNoDocumentOverflow(page);
});

test('文字和语音面试的核心控制区在手机视口内可达', async ({ page }) => {
  await page.route('https://cdn.jsdelivr.net/**', route => route.abort());
  await page.addInitScript(() => {
    class FakeWebSocket extends EventTarget {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;
      readonly CONNECTING = FakeWebSocket.CONNECTING;
      readonly OPEN = FakeWebSocket.OPEN;
      readonly CLOSING = FakeWebSocket.CLOSING;
      readonly CLOSED = FakeWebSocket.CLOSED;
      readyState = FakeWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(_url: string) {
        super();
        window.setTimeout(() => {
          this.readyState = FakeWebSocket.OPEN;
          this.onopen?.(new Event('open'));
          this.onmessage?.(new MessageEvent('message', {
            data: JSON.stringify({ type: 'control', action: 'asr_ready' }),
          }));
        }, 0);
      }

      send() {}

      close() {
        this.readyState = FakeWebSocket.CLOSED;
      }
    }

    window.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  });
  await installApiRoutes(page);

  await page.goto('/interview/session/mobile-session');
  const workspace = page.getByTestId('interview-workspace');
  const composer = page.getByTestId('interview-composer');
  await expect(workspace).toBeVisible();
  await expect(composer).toBeVisible();
  const [workspaceBox, composerBox] = await Promise.all([workspace.boundingBox(), composer.boundingBox()]);
  expect(workspaceBox).not.toBeNull();
  expect(composerBox).not.toBeNull();
  expect(workspaceBox!.width).toBeLessThanOrEqual(360);
  expect(composerBox!.y + composerBox!.height).toBeLessThanOrEqual(800);
  await expectNoDocumentOverflow(page);

  await page.goto('/voice-interview?skillId=java-backend&duration=15');
  await expect(page.getByRole('heading', { name: '语音模拟面试' })).toBeVisible();
  await expect(page.getByTestId('voice-recorder-toggle')).toBeVisible();
  await expect(page.getByTestId('voice-submit-answer')).toBeVisible();
  await expect(page.getByText('对话实录')).toBeVisible();
  await expectNoDocumentOverflow(page);
});

test('公开账号页面和目标视口均无文档级横向滚动', async ({ page }) => {
  await installApiRoutes(page, true);
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: '登录 AI Interview' })).toBeVisible();
  await expectNoDocumentOverflow(page);

  await page.unroute(API_ROUTE);
  await installApiRoutes(page);
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: '简历管理' })).toBeVisible();
    await expectNoDocumentOverflow(page);
  }
});
