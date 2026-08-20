import { expect, test } from '@playwright/test';

const runRealBackend = process.env.RUN_REAL_BACKEND_E2E === 'true';
const backendUrl = process.env.REAL_BACKEND_URL ?? 'http://127.0.0.1:28080';

test.describe('真实 Python 后端 @real-backend', () => {
  test.skip(!runRealBackend, 'RUN_REAL_BACKEND_E2E is not enabled');

  test('面试日程真实 API 数据会显示在现有页面', async ({ page, request }) => {
    const created = await request.post(`${backendUrl}/api/interview-schedule`, {
      data: {
        companyName: 'Playwright Real Backend Corp',
        position: 'Backend Engineer',
        interviewTime: '2026-08-17T10:30:00',
        interviewType: 'VIDEO',
        roundNumber: 1,
        notes: 'real-backend-e2e',
      },
    });
    expect(created.ok()).toBe(true);
    const createdSchedule = await created.json() as { id: number; companyName: string; position: string };
    expect(createdSchedule).toMatchObject({
      companyName: 'Playwright Real Backend Corp',
      position: 'Backend Engineer',
    });

    try {
      await page.goto('/interview-schedule');

      await expect(page.getByText('Playwright Real Backend Corp').first()).toBeVisible();
      await expect(page.getByText('Backend Engineer').first()).toBeVisible();
    } finally {
      const deleted = await request.delete(
        `${backendUrl}/api/interview-schedule/${createdSchedule.id}`,
      );
      expect(deleted.ok()).toBe(true);
    }
  });

  test('设置页读取真实 Provider 并自动发现模型列表', async ({ page, request }) => {
    const providersResponse = await request.get(`${backendUrl}/api/llm-provider/list`);
    expect(providersResponse.ok()).toBe(true);
    const providers = await providersResponse.json() as { id: string; model: string }[];
    const dashscope = providers.find(provider => provider.id === 'dashscope');
    expect(dashscope).toBeDefined();

    const modelsResponse = await request.post(
      `${backendUrl}/api/llm-provider/models/discover`,
      { data: { providerId: 'dashscope' } },
    );
    expect(modelsResponse.ok()).toBe(true);
    const models = await modelsResponse.json() as {
      chatModels: string[];
      embeddingModels: string[];
      source: 'remote' | 'configured';
      warning: string | null;
    };
    expect(models.chatModels).toContain(dashscope!.model);
    expect(['remote', 'configured']).toContain(models.source);

    await page.goto('/settings');

    await expect(page.getByText('DashScope', { exact: false }).first()).toBeVisible();
    await expect(page.getByText(dashscope!.model, { exact: false }).first()).toBeVisible();

    const dashscopeCard = page.getByRole('heading', { name: 'dashscope', exact: true })
      .locator('xpath=ancestor::div[contains(@class, "min-h-")][1]');
    await dashscopeCard.getByRole('button', { name: '编辑', exact: true }).click();
    await expect(page.getByRole('heading', { name: '编辑 Provider' })).toBeVisible();
    const apiKeyLabel = page.locator('label').filter({ hasText: 'API Key' }).first();
    await expect(apiKeyLabel.locator('span.text-red-500')).toHaveText('*');
    await expect(page.getByText(/已获取 \d+ 个聊天模型|当前仅显示已配置模型/)).toBeVisible();

    const chatModelInput = page.getByPlaceholder('从 Provider 拉取列表，或输入自定义聊天模型名');
    await chatModelInput.click();
    await expect(page.getByRole('button', { name: dashscope!.model, exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /qwen.*(?:asr|tts|image)/i })).toHaveCount(0);
  });
});
