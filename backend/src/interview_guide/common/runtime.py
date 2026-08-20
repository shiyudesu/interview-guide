from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
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

    async def run(
        self,
        function: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        if not self._accepting:
            raise RuntimeError("Blocking executor is shutting down")
        loop = asyncio.get_running_loop()
        call = partial(function, *args, **kwargs)
        return await loop.run_in_executor(self._executor, call)

    async def shutdown(self) -> None:
        self._accepting = False
        loop = asyncio.get_running_loop()
        completed: asyncio.Future[None] = loop.create_future()

        def close_executor() -> None:
            try:
                self._executor.shutdown(
                    wait=True,
                    cancel_futures=True,
                )
            except BaseException as error:
                loop.call_soon_threadsafe(completed.set_exception, error)
            else:
                loop.call_soon_threadsafe(completed.set_result, None)

        threading.Thread(
            target=close_executor,
            name="interview-guide-executor-shutdown",
        ).start()
        await completed
