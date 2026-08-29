import assert from 'node:assert/strict';
import test from 'node:test';

import {createRequestId} from './requestId.ts';

test('可信环境优先使用浏览器 randomUUID', () => {
  const expected = '11111111-2222-4333-8444-555555555555';
  let fallbackCalled = false;

  const actual = createRequestId({
    randomUUID: () => expected,
    getRandomValues: array => {
      fallbackCalled = true;
      return array;
    },
  });

  assert.equal(actual, expected);
  assert.equal(fallbackCalled, false);
});

test('明文内网 HTTP 缺少 randomUUID 时生成 UUID v4', () => {
  const source = Uint8Array.from([
    0x00, 0x11, 0x22, 0x33,
    0x44, 0x55,
    0x66, 0x77,
    0xff, 0x99,
    0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
  ]);

  const actual = createRequestId({
    getRandomValues: array => {
      array.set(source);
      return array;
    },
  });

  assert.equal(actual, '00112233-4455-4677-bf99-aabbccddeeff');
  assert.match(actual, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});
