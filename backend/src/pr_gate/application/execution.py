from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

Worker = Callable[[str], Coroutine[Any, Any, None]]


class AnalysisExecutionService:
    """Tracks only local tasks; persistence remains the source of truth for reports."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, analysis_id: str, worker: Worker) -> None:
        task: asyncio.Task[None] = asyncio.create_task(
            worker(analysis_id), name=f"analysis-{analysis_id}"
        )
        self._tasks[analysis_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(analysis_id, None))

    async def stop(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
