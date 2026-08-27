import { expect, test, type Page } from '@playwright/test';

const providers = [
  {
    id: 'dashscope',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    maskedApiKey: 'sk-****cope',
    hasApiKey: true,
    model: 'qwen3.7-max',
    embeddingModel: 'qwen3.7-text-embedding',
    embeddingDimensions: 1024,
    supportsEmbedding: true,
    temperature: 0.7,
    defaultChatProvider: true,
    defaultEmbeddingProvider: true,
  },
  {
    id: 'custom-openai',
    baseUrl: 'https://example.test/v1',
    maskedApiKey: 'sk-****stom',
    hasApiKey: true,
    model: 'interview-model-v2',
    embeddingModel: 'embedding-model-v2',
    embeddingDimensions: 1024,
    supportsEmbedding: true,
    temperature: 0.5,
    defaultChatProvider: false,
    defaultEmbeddingProvider: false,
  },
];

async function installCommonRoutes(page: Page) {
  let defaultChatProvider = 'dashscope';
  let defaultEmbeddingProvider = 'dashscope';

  await page.route('**/api/auth/config', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ authEnabled: false, registrationEnabled: false }),
  }));
  await page.route('**/api/llm-provider/list', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(providers.map(provider => ({
      ...provider,
      defaultChatProvider: provider.id === defaultChatProvider,
      defaultEmbeddingProvider: provider.id === defaultEmbeddingProvider,
    }))),
  }));
  await page.route('**/api/llm-provider/default-provider', async route => {
    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as {
        defaultProvider: string;
        defaultEmbeddingProvider: string;
      };
      defaultChatProvider = payload.defaultProvider;
      defaultEmbeddingProvider = payload.defaultEmbeddingProvider;
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        defaultProvider: defaultChatProvider,
        defaultEmbeddingProvider,
      }),
    });
  });
  await page.route('**/api/llm-provider/default-embedding-provider', async route => {
    const payload = route.request().postDataJSON() as {
      defaultProvider: string;
      defaultEmbeddingProvider: string;
    };
    defaultChatProvider = payload.defaultProvider;
    defaultEmbeddingProvider = payload.defaultEmbeddingProvider;
    await route.fulfill({ status: 204, body: '' });
  });
  await page.route('**/api/llm-provider/voice/asr', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
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
    }),
  }));
  await page.route('**/api/llm-provider/voice/tts', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
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
    }),
  }));

  return {
    defaults: () => ({ defaultChatProvider, defaultEmbeddingProvider }),
  };
}

test.describe('Provider 选择可见性', () => {
  test('面试页展示账号默认 Provider，并允许本次面试覆盖', async ({ page }) => {
    await installCommonRoutes(page);
    await page.route('**/api/interview/skills', route => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([{
        id: 'java-backend',
        name: 'Java 后端',
        description: 'Java 后端开发面试',
        categories: [],
        isPreset: true,
        sourceJd: null,
      }]),
    }));
    await page.route('**/api/resumes**', route => route.fulfill({
      contentType: 'application/json',
      body: '[]',
    }));
    await page.route('**/api/voice-interview/sessions**', route => route.fulfill({
      contentType: 'application/json',
      body: '[]',
    }));
    await page.route('**/api/interview/sessions**', async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            sessionId: 'provider-selection-session',
            channel: 'TEXT',
            status: 'IN_PROGRESS',
            currentQuestion: {
              questionId: 'question-1',
              kind: 'MAIN',
              parentQuestionId: null,
              question: '请介绍一下你最熟悉的项目。',
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
          }),
        });
        return;
      }
      await route.fulfill({ contentType: 'application/json', body: '[]' });
    });

    await page.goto('/interview-hub');

    await expect(page.getByText('dashscope · qwen3.7-max', { exact: true })).toBeVisible();
    await expect(page.getByText('跟随账号默认设置', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: '更换', exact: true }).click();
    await page.getByRole('button', { name: '本次面试 Provider', exact: true }).click();
    await page.getByRole('option', { name: /custom-openai/ }).click();

    await expect(page.locator('p').filter({ hasText: 'custom-openai · interview-model-v2' })).toBeVisible();
    await expect(page.getByText('仅本次面试覆盖账号默认设置', { exact: true })).toBeVisible();

    const createRequest = page.waitForRequest(request => (
      request.method() === 'POST'
      && new URL(request.url()).pathname === '/api/interview/sessions'
    ));
    await page.getByRole('button', { name: '开始文字面试', exact: true }).click();
    const request = await createRequest;
    expect(request.postDataJSON()).toMatchObject({ llmProvider: 'custom-openai' });
  });

  test('设置页在顶部集中展示并修改默认聊天和向量 Provider', async ({ page }) => {
    const state = await installCommonRoutes(page);

    await page.goto('/settings');

    await expect(page.getByRole('heading', { name: '默认模型服务', exact: true })).toBeVisible();
    const chatProvider = page.getByRole('button', { name: '默认聊天 Provider', exact: true });
    const embeddingProvider = page.getByRole('button', { name: '默认向量 Provider', exact: true });
    await expect(chatProvider).toContainText('dashscope');
    await expect(embeddingProvider).toContainText('dashscope');

    await chatProvider.click();
    await page.getByRole('option', { name: /custom-openai.*interview-model-v2/ }).click();
    await expect(page.getByRole('heading', { name: '设为默认聊天服务' })).toBeVisible();
    await page.getByRole('button', { name: '确认设置', exact: true }).click();
    await expect(chatProvider).toContainText('custom-openai');
    expect(state.defaults().defaultChatProvider).toBe('custom-openai');

    await embeddingProvider.click();
    await page.getByRole('option', { name: /custom-openai.*embedding-model-v2/ }).click();
    await expect(page.getByRole('heading', { name: '设为默认向量服务' })).toBeVisible();
    await page.getByRole('button', { name: '确认设置', exact: true }).click();
    await expect(embeddingProvider).toContainText('custom-openai');
    expect(state.defaults().defaultEmbeddingProvider).toBe('custom-openai');
  });
});
