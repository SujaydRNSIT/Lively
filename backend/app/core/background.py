"""
Run side effects (email, persistence, CRM sync) off the voice turn's hot path.

Inside the server these never block the event loop. Without a running loop (plain scripts and sync
tests) blocking work runs inline and coroutine work is skipped.
"""
import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Set

logger = logging.getLogger("lively.background")

_tasks: Set[asyncio.Future] = set()


def _track(fut: asyncio.Future, on_result: Optional[Callable[[Any], None]] = None) -> None:
    _tasks.add(fut)

    def _done(f: asyncio.Future):
        _tasks.discard(f)
        if f.cancelled():
            return
        exc = f.exception()
        if exc:
            logger.warning(f"Background task failed: {exc!r}")
            return
        if on_result:
            try:
                on_result(f.result())
            except Exception as cb_err:
                logger.warning(f"Background callback failed: {cb_err!r}")

    fut.add_done_callback(_done)


def run_blocking(fn: Callable[..., Any], *args, on_result: Optional[Callable[[Any], None]] = None, **kwargs) -> None:
    """Run a blocking function in the default thread pool; inline when no event loop is running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            result = fn(*args, **kwargs)
            if on_result:
                on_result(result)
        except Exception as e:
            logger.warning(f"Inline task failed: {e!r}")
        return
    _track(loop.run_in_executor(None, functools.partial(fn, *args, **kwargs)), on_result)


def spawn(coro_fn: Callable[..., Any], *args, **kwargs) -> None:
    """Schedule a coroutine function as a tracked task. Skipped when no event loop is running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _track(loop.create_task(coro_fn(*args, **kwargs)))


async def drain(timeout: float = 5.0) -> None:
    """Wait for pending background work (used by tests and graceful shutdown)."""
    pending = [t for t in list(_tasks) if not t.done()]
    if pending:
        await asyncio.wait(pending, timeout=timeout)
