import { expect, test, type Page, type Route } from '@playwright/test';

const knowledgeBase = {
  id: 17,
  name: 'OpenTrek 预置知识库',
  category: '分布式系统',
  originalFilename: 'distributed-systems.md',
  fileSize: 2048,
  contentType: 'text/markdown',
  uploadedAt: '2026-08-28T08:00:00',
  lastAccessedAt: '2026-08-28T09:00:00',
  accessCount: 1,
  questionCount: 2,
  vectorStatus: 'FAILED',
  vectorError: 'local vectors are intentionally unavailable',
  chunkCount: 0,
  questionGenStatus: 'NONE',
  questionGenError: null,
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installCompetitionApi(page: Page) {
  const requested: string[] = [];
  page.on('request', request => requested.push(new URL(request.url()).pathname));
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') {
      return json(route, {
        authEnabled: false,
        registrationEnabled: false,
        competitionMode: true,
      });
    }
    if (path === '/api/resumes') return json(route, []);
    if (path === '/api/interview/skills') return json(route, []);
    if (path === '/api/interview/sessions') return json(route, []);
    if (path === '/api/knowledgebase/stats') {
      return json(route, {
        totalCount: 1,
        totalQuestionCount: 0,
        totalAccessCount: 1,
        completedCount: 1,
        processingCount: 0,
      });
    }
    if (path === '/api/knowledgebase/list') return json(route, [knowledgeBase]);
    if (path === '/api/knowledgebase/categories') return json(route, ['分布式系统']);
    return json(route, []);
  });
  return requested;
}

test.describe('OpenTrek 校园赛版', () => {
  test('隐藏语音、Provider 和受限直达路由', async ({ page }) => {
    const requested = await installCompetitionApi(page);

    await page.goto('/interview-hub');

    await expect(page.getByText('OpenTrek 校园赛版').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('语音面试', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /设置/ })).toHaveCount(0);
    expect(requested.some(path => path.startsWith('/api/llm-providers'))).toBe(false);
    expect(requested.some(path => path.startsWith('/api/voice-interview'))).toBe(false);

    for (const path of ['/settings', '/voice-interview', '/knowledgebase/upload']) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/interview-hub$/);
    }
  });

  test('知识库管理只保留读取和下载操作', async ({ page }) => {
    await installCompetitionApi(page);

    await page.goto('/knowledgebase');

    await expect(page.getByRole('table').getByText('OpenTrek 预置知识库')).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole('button', { name: '上传知识库' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '重新向量化' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0);
    await expect(page.getByTitle('编辑分类')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '下载' })).toBeVisible();
  });
});
