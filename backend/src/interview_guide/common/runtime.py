from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")


class BlockingExecutor:
    def __init__(self, max_workers: int) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="interview-guide-blocking",
        )
        self._accepting = True

    @property
    def accepting(self) -> bool:
        return self._accepting

    async def run(self, function: Callable[..., T], *args: Any) -> T:
        if not self._accepting:
            raise RuntimeError("Blocking executor is shutting down")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, function, *args)

    async def shutdown(self) -> None:
        self._accepting = False
        await asyncio.to_thread(
            self._executor.shutdown,
            wait=True,
            cancel_futures=True,
        )
