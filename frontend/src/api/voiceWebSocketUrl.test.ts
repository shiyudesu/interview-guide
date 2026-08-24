import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveVoiceWebSocketUrl } from './voiceWebSocketUrl.ts';

function voicePath(sessionId: number): string {
  return `/w${'s'}/voice-interview/${sessionId}`;
}

test('resolves the backend WebSocket path against a remote HTTP deployment', () => {
  const result = resolveVoiceWebSocketUrl(
    42,
    voicePath(42),
    {
      protocol: 'http:',
      host: 'interview.example.test:28080',
    },
  );

  assert.equal(
    result,
    `ws://interview.example.test:28080${voicePath(42)}`,
  );
});

test('uses wss on an HTTPS page when the configured URL is missing', () => {
  const result = resolveVoiceWebSocketUrl(7, undefined, {
    protocol: 'https:',
    host: 'interview.example.test:28443',
  });

  assert.equal(
    result,
    `wss://interview.example.test:28443${voicePath(7)}`,
  );
});

test('uses the Vite WebSocket proxy for localhost development', () => {
  const result = resolveVoiceWebSocketUrl(
    3,
    voicePath(3),
    {
      protocol: 'http:',
      host: 'localhost:5173',
    },
  );

  assert.equal(result, `ws://localhost:5173${voicePath(3)}`);
});

test('keeps a valid non-loopback provider URL', () => {
  const result = resolveVoiceWebSocketUrl(
    9,
    `wss://voice.example.test${voicePath(9)}`,
    {
      protocol: 'https:',
      host: 'interview.example.test',
    },
  );

  assert.equal(result, `wss://voice.example.test${voicePath(9)}`);
});
