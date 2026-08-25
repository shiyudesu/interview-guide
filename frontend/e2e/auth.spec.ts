import { expect, test, type Page, type Route } from '@playwright/test';

const USER = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'alice@example.test',
  displayName: 'Alice',
  role: 'USER',
  status: 'ACTIVE',
  createdAt: '2026-08-25T00:00:00',
};
const CSRF_TOKEN = 'csrf-test-token';

async function installAuthRoutes(page: Page) {
  let authenticated = false;

  await page.route('**/api/auth/config', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ authEnabled: true, registrationEnabled: false }),
  }));
  await page.route('**/api/auth/me', route => {
    if (!authenticated) {
      return route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ code: 1001, detail: '登录状态无效或已过期' }),
      });
    }
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ user: USER, csrfToken: CSRF_TOKEN }),
    });
  });
  await page.route('**/api/auth/login', async route => {
    const payload = route.request().postDataJSON() as { email: string; password: string };
    expect(payload).toEqual({ email: USER.email, password: 'correct horse battery staple' });
    authenticated = true;
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ user: USER, csrfToken: CSRF_TOKEN }),
    });
  });

  return {
    logout: (handler: (route: Route) => Promise<void>) => page.route('**/api/auth/logout', handler),
  };
}

test.describe('账号与路由保护', () => {
  test('未登录会跳转登录，登录后返回原页面，退出请求携带 CSRF', async ({ page }) => {
    const routes = await installAuthRoutes(page);
    await routes.logout(async route => {
      expect(route.request().headers()['x-csrf-token']).toBe(CSRF_TOKEN);
      await route.fulfill({ status: 204, body: '' });
    });

    await page.goto('/account');
    await expect(page).toHaveURL(/\/login$/);

    await page.getByLabel('邮箱').fill(USER.email);
    await page.getByLabel('密码', { exact: true }).fill('correct horse battery staple');
    await page.getByRole('button', { name: '登录', exact: true }).click();

    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByText(USER.email).first()).toBeVisible();
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('注册关闭时显示明确提示且不能提交', async ({ page }) => {
    await installAuthRoutes(page);
    await page.goto('/register');

    await expect(page.getByText('当前未开放自助注册，请联系管理员创建账号。')).toBeVisible();
    await expect(page.getByRole('button', { name: '注册并继续' })).toBeDisabled();
  });

  test('邮箱验证和密码找回页面完成公开账号流程', async ({ page }) => {
    await installAuthRoutes(page);
    await page.route('**/api/auth/email/verification/confirm', async route => {
      expect(route.request().postDataJSON()).toEqual({ token: 'verify-token' });
      await route.fulfill({ status: 204, body: '' });
    });
    await page.route('**/api/auth/password/reset/request', async route => {
      expect(route.request().postDataJSON()).toEqual({ email: USER.email });
      await route.fulfill({ status: 204, body: '' });
    });
    await page.route('**/api/auth/password/reset/confirm', async route => {
      expect(route.request().postDataJSON()).toEqual({
        token: 'reset-token',
        newPassword: 'replacement horse battery staple',
      });
      await route.fulfill({ status: 204, body: '' });
    });

    await page.goto('/verify-email?token=verify-token');
    await expect(page.getByText('邮箱验证成功，现在可以登录了。')).toBeVisible();

    await page.goto('/forgot-password');
    await page.getByLabel('邮箱').fill(USER.email);
    await page.getByRole('button', { name: '发送重置邮件' }).click();
    await expect(page.getByText('如果该邮箱对应可用账号，密码重置邮件已经发送。')).toBeVisible();

    await page.goto('/reset-password?token=reset-token');
    await page.getByLabel('新密码', { exact: true }).fill('replacement horse battery staple');
    await page.getByLabel('确认新密码').fill('replacement horse battery staple');
    await page.getByRole('button', { name: '重置密码' }).click();
    await expect(page.getByText('密码已重置，所有旧 Session 均已撤销。')).toBeVisible();
  });
});
