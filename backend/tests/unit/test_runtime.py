from __future__ import annotations

import asyncio
import time

import pytest

from interview_guide.common.runtime import BlockingExecutor
from interview_guide.scheduler import run_scheduler
from interview_guide.worker import run_worker


@pytest.mark.asyncio
async def test_blocking_operation_does_not_block_event_loop() -> None:
    executor = BlockingExecutor(max_workers=1)
    ticked = asyncio.Event()

    async def ticker() -> None:
        await asyncio.sleep(0.01)
        ticked.set()

    blocking = asyncio.create_task(executor.run(time.sleep, 0.05))
    ticker_task = asyncio.create_task(ticker())
    await asyncio.wait_for(ticked.wait(), timeout=0.03)
    await blocking
    await ticker_task
    await executor.shutdown()


@pytest.mark.asyncio
async def test_executor_rejects_new_work_after_shutdown() -> None:
    executor = BlockingExecutor(max_workers=1)
    await executor.shutdown()

    with pytest.raises(RuntimeError, match="shutting down"):
        await executor.run(lambda: None)


@pytest.mark.asyncio
async def test_worker_and_scheduler_stop_when_event_is_set() -> None:
    worker_stop = asyncio.Event()
    worker_stop.set()
    scheduler_stop = asyncio.Event()
    scheduler_stop.set()

    await asyncio.wait_for(run_worker(worker_stop), timeout=1)
    await asyncio.wait_for(run_scheduler(scheduler_stop), timeout=1)
