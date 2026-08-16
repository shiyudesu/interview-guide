import { expect, test } from '@playwright/test';

const SESSION_ID = 42;
const USER_SUBTITLE = '我负责订单系统的幂等设计。';
const AI_FOLLOW_UP = '请具体说明你如何处理重复提交。';
const NEXT_USER_SUBTITLE = '当前这一轮我会使用唯一索引保证幂等。';

test.describe('语音面试', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('https://cdn.jsdelivr.net/**', route => route.abort());

    await page.addInitScript(() => {
      type SocketMessage = {
        type: string;
        action?: string;
        data?: Record<string, unknown>;
      };

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
          (window as Window & { __voiceTestReceive?: (payload: unknown) => void })
            .__voiceTestReceive = payload => this.receive(payload);
          window.setTimeout(() => {
            this.readyState = FakeWebSocket.OPEN;
            this.onopen?.(new Event('open'));
            this.receive({ type: 'control', action: 'asr_ready' });
          }, 0);
        }

        send(payload: string) {
          const message = JSON.parse(payload) as SocketMessage;
          const sent = ((window as Window & { __voiceTestSentMessages?: SocketMessage[] })
            .__voiceTestSentMessages ??= []);
          sent.push(message);

          if (message.type === 'audio') {
            this.receive({ type: 'subtitle', text: '我负责订单系统的幂等设计。', isFinal: false });
          }
          if (message.type === 'control' && message.action === 'submit') {
            this.receive({ type: 'audio', data: '', text: '请具体说明你如何处理重复提交。' });
          }
        }

        close() {
          this.readyState = FakeWebSocket.CLOSED;
          this.onclose?.({ code: 1000, wasClean: true } as CloseEvent);
        }

        private receive(payload: unknown) {
          this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }));
        }
      }

      Object.assign(FakeWebSocket, {
        CONNECTING: FakeWebSocket.CONNECTING,
        OPEN: FakeWebSocket.OPEN,
        CLOSING: FakeWebSocket.CLOSING,
        CLOSED: FakeWebSocket.CLOSED,
      });
      window.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
      window.vad = {
        MicVAD: {
          new: async () => ({
            start: async () => undefined,
            pause: () => undefined,
            destroy: () => undefined,
          }),
        },
      };
    });

    await page.route('**/api/interview/skills', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          code: 200,
          message: 'success',
          data: [{ id: 'java-backend', name: 'Java 后端', description: '', categories: [], isPreset: true, sourceJd: null }],
        }),
      });
    });
    await page.route('**/api/voice-interview/sessions', async route => {
      if (route.request().method() !== 'POST') return route.fallback();
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          code: 200,
          message: 'success',
          data: {
            sessionId: 42,
            roleType: 'JAVA_BACKEND',
            currentPhase: 'TECH',
            status: 'IN_PROGRESS',
            startTime: '2026-08-03T00:00:00Z',
            plannedDuration: 15,
            webSocketUrl: 'ws://voice-test.local/42',
          },
        }),
      });
    });
    await page.route(`**/api/voice-interview/sessions/${SESSION_ID}/end`, async route => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ code: 200, message: 'success', data: {} }) });
    });
  });

  test('将虚拟麦克风音频发送到服务端，并展示字幕和 AI 追问', async ({ page }) => {
    await page.goto('/voice-interview?skillId=java-backend&duration=15');

    const recordButton = page.getByTestId('voice-recorder-toggle');
    await expect(recordButton).toBeEnabled();
    await recordButton.click();

    await expect(page.getByTestId('voice-current-user-text')).toHaveText(USER_SUBTITLE);
    await page.getByTestId('voice-submit-answer').click();
    await expect(page.getByTestId('voice-current-ai-text')).toHaveText(AI_FOLLOW_UP);

    await expect.poll(async () => page.evaluate(() =>
      (window as Window & { __voiceTestSentMessages?: { type: string }[] }).__voiceTestSentMessages
        ?.some(message => message.type === 'audio') ?? false,
    )).toBe(true);
  });

  test('提交后迟到的上一轮字幕不会污染下一轮回答', async ({ page }) => {
    await page.goto('/voice-interview?skillId=java-backend&duration=15');

    const recordButton = page.getByTestId('voice-recorder-toggle');
    await expect(recordButton).toBeEnabled();
    await recordButton.click();
    await expect(page.getByTestId('voice-current-user-text')).toHaveText(USER_SUBTITLE);

    await page.getByTestId('voice-submit-answer').click();
    await expect(page.getByTestId('voice-current-ai-text')).toHaveText(AI_FOLLOW_UP);
    await page.evaluate((lateText) => {
      (window as Window & { __voiceTestReceive?: (payload: unknown) => void })
        .__voiceTestReceive?.({ type: 'subtitle', text: lateText, isFinal: false });
    }, USER_SUBTITLE);

    await expect(page.getByTestId('voice-current-ai-text')).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('voice-current-user-text')).not.toBeVisible();

    await page.evaluate((nextText) => {
      (window as Window & { __voiceTestReceive?: (payload: unknown) => void })
        .__voiceTestReceive?.({ type: 'subtitle', text: nextText, isFinal: false });
    }, NEXT_USER_SUBTITLE);
    await expect(page.getByTestId('voice-current-user-text')).toHaveText(NEXT_USER_SUBTITLE);
    await expect(page.getByTestId('voice-submit-answer')).toBeEnabled();
    await page.getByTestId('voice-submit-answer').click();

    await expect.poll(async () => page.evaluate((nextText) =>
      (window as Window & {
        __voiceTestSentMessages?: { type: string; action?: string; data?: { text?: string } }[];
      }).__voiceTestSentMessages?.some(message =>
        message.type === 'control' && message.action === 'submit' && message.data?.text === nextText
      ) ?? false,
    NEXT_USER_SUBTITLE)).toBe(true);
  });

  test('结束面试后返回面试记录页', async ({ page }) => {
    await page.goto('/voice-interview?skillId=java-backend&duration=15');

    await page.getByTestId('voice-end-interview').click();
    await expect(page).toHaveURL(/\/interviews$/);
  });
});
