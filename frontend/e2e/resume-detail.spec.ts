import { expect, test } from '@playwright/test';

test.describe('简历详情契约', () => {
  test('展示后端返回的分析和面试记录', async ({ page }) => {
    await page.route('**/api/auth/config', route => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ authEnabled: false, registrationEnabled: false }),
    }));
    await page.route('**/api/resumes/7/detail', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: 7,
          filename: 'backend-resume.pdf',
          fileSize: 128,
          contentType: 'application/pdf',
          storageUrl: null,
          uploadedAt: '2026-08-22T10:30:00',
          accessCount: 1,
          resumeText: 'Python backend engineer',
          analyzeStatus: 'COMPLETED',
          analyzeError: null,
          analyses: [
            {
              id: 11,
              overallScore: 86,
              contentScore: 13,
              structureScore: 12,
              skillMatchScore: 18,
              expressionScore: 8,
              projectScore: 35,
              summary: '整体较强',
              analyzedAt: '2026-08-22T10:30:00',
              strengths: ['工程经验扎实'],
              suggestions: [],
            },
          ],
          interviews: [
            {
              id: 19,
              sessionId: 'session-contract',
              channel: 'TEXT',
              plannedMainQuestions: 6,
              status: 'EVALUATED',
              evaluateStatus: 'COMPLETED',
              evaluateError: null,
              overallScore: 88,
              overallFeedback: '回答完整',
              createdAt: '2026-08-22T10:30:00',
              completedAt: '2026-08-22T10:30:00',
              strengths: ['表达清晰'],
              improvements: ['补充取舍分析'],
            },
          ],
        }),
      });
    });

    await page.goto('/history/7');

    await expect(page.getByText('整体较强')).toBeVisible();
    await page.getByRole('button', { name: /面试记录/ }).click();
    await expect(page.getByText('共 1 场练习')).toBeVisible();
    await expect(page.getByText('模拟面试 #1')).toBeVisible();
    await expect(page.getByText('88')).toBeVisible();
  });
});
