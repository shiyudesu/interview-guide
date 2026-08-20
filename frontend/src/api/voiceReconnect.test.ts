import assert from 'node:assert/strict';
import test from 'node:test';
import { ReconnectTimer } from './voiceReconnect.ts';

function wait(milliseconds: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

test('stop cancels a pending reconnect callback', async () => {
  const timer = new ReconnectTimer();
  let reconnects = 0;
  timer.schedule(5, () => reconnects++);
  timer.stop();

  await wait(15);

  assert.equal(reconnects, 0);
});

test('activate allows reconnect scheduling after a previous stop', async () => {
  const timer = new ReconnectTimer();
  let reconnects = 0;
  timer.stop();
  timer.activate();
  timer.schedule(5, () => reconnects++);

  await wait(15);

  assert.equal(reconnects, 1);
});
