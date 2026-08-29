import fs from 'node:fs';

import { expect, test, type Page } from '@playwright/test';

interface CampusAccount {
  email: string;
  password: string;
  role: 'ADMIN' | 'USER';
}

interface KnowledgeBaseRecord {
  id: number;
  name: string;
}

const credentialsFile = process.env.CAMPUS_E2E_CREDENTIALS_FILE;
const enabled = Boolean(credentialsFile && fs.existsSync(credentialsFile));
const accounts = enabled
  ? (JSON.parse(fs.readFileSync(credentialsFile!, 'utf8')) as CampusAccount[])
  : [];
const judges = accounts.filter(account => account.role === 'USER').slice(0, 2);

test.use({ baseURL: process.env.CAMPUS_E2E_BASE_URL ?? 'http://127.0.0.1:18073' });

async function login(page: Page, account: CampusAccount) {
  await page.goto('/login');
  await page.getByPlaceholder('you@example.com').fill(account.email);
  await page.locator('#login-password').fill(account.password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page.getByText('OpenTrek 校园赛版').first()).toBeVisible();
}

test.describe('OpenTrek 校园实例真实后端 @real-backend', () => {
  test.skip(!enabled || judges.length !== 2, '需要两个受保护的校园评委账号');

  test('两个评委并发登录、只读入口和知识库所有权隔离', async ({ browser }) => {
    const firstContext = await browser.newContext();
    const secondContext = await browser.newContext();
    const firstPage = await firstContext.newPage();
    const secondPage = await secondContext.newPage();

    try {
      await Promise.all([login(firstPage, judges[0]), login(secondPage, judges[1])]);

      for (const page of [firstPage, secondPage]) {
        await expect(page.getByText('语音面试', { exact: true })).toHaveCount(0);
        await expect(page.getByRole('link', { name: /设置/ })).toHaveCount(0);
        await page.goto('/knowledgebase');
        await expect(page.getByRole('table').getByText('OpenTrek 校园技术资料')).toBeVisible();
        await expect(page.getByRole('button', { name: '上传知识库' })).toHaveCount(0);
        await expect(page.getByRole('button', { name: '重新向量化' })).toHaveCount(0);
        await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0);
      }

      const [firstResponse, secondResponse] = await Promise.all([
        firstPage.request.get('/api/knowledgebase/list'),
        secondPage.request.get('/api/knowledgebase/list'),
      ]);
      expect(firstResponse.ok()).toBeTruthy();
      expect(secondResponse.ok()).toBeTruthy();
      const firstRecords = (await firstResponse.json()) as KnowledgeBaseRecord[];
      const secondRecords = (await secondResponse.json()) as KnowledgeBaseRecord[];
      const firstRecord = firstRecords.find(item => item.name === 'OpenTrek 校园技术资料');
      const secondRecord = secondRecords.find(item => item.name === 'OpenTrek 校园技术资料');
      expect(firstRecord).toBeDefined();
      expect(secondRecord).toBeDefined();
      expect(firstRecord!.id).not.toBe(secondRecord!.id);

      const [firstCrossRead, secondCrossRead] = await Promise.all([
        firstPage.request.get(`/api/knowledgebase/${secondRecord!.id}`),
        secondPage.request.get(`/api/knowledgebase/${firstRecord!.id}`),
      ]);
      expect(firstCrossRead.status()).toBe(404);
      expect(secondCrossRead.status()).toBe(404);
    } finally {
      await firstContext.close();
      await secondContext.close();
    }
  });
});
