import assert from 'node:assert/strict';
import test from 'node:test';
import { authenticatedStreamInit } from './streamSecurity.ts';

test('流式 POST 请求携带 CSRF Token 和会话 Cookie', () => {
  const init = authenticatedStreamInit(
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    },
    'stream-csrf-token',
  );
  const headers = new Headers(init.headers);

  assert.equal(headers.get('Content-Type'), 'application/json');
  assert.equal(headers.get('X-CSRF-Token'), 'stream-csrf-token');
  assert.equal(init.credentials, 'include');
});

test('流式安全读取请求不附加 CSRF Token', () => {
  const init = authenticatedStreamInit({ method: 'GET' }, 'stream-csrf-token');
  const headers = new Headers(init.headers);

  assert.equal(headers.get('X-CSRF-Token'), null);
  assert.equal(init.credentials, 'include');
});
