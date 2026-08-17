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
    expect(await created.json()).toMatchObject({
      code: 200,
      data: {
        companyName: 'Playwright Real Backend Corp',
        position: 'Backend Engineer',
      },
    });

    await page.goto('/interview-schedule');

    await expect(page.getByText('Playwright Real Backend Corp').first()).toBeVisible();
    await expect(page.getByText('Backend Engineer').first()).toBeVisible();
  });

  test('设置页读取真实 Provider 列表', async ({ page, request }) => {
    const providersResponse = await request.get(`${backendUrl}/api/llm-provider/list`);
    expect(providersResponse.ok()).toBe(true);
    const providers = await providersResponse.json() as {
      data: { id: string; model: string }[];
    };
    const dashscope = providers.data.find(provider => provider.id === 'dashscope');
    expect(dashscope).toBeDefined();

    await page.goto('/settings');

    await expect(page.getByText('DashScope', { exact: false }).first()).toBeVisible();
    await expect(page.getByText(dashscope!.model, { exact: false }).first()).toBeVisible();
  });
});
