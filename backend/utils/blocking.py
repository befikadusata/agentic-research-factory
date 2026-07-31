"""Run blocking calls on threads the event loop will never wait for.

`asyncio.to_thread` and `loop.run_in_executor(None, ...)` both submit to the
loop's *default* ThreadPoolExecutor. Cancelling the awaitable — all that
`asyncio.wait_for` does on timeout — cancels the wrapper only; the worker thread
keeps running. Both `asyncio.run()` (via `loop.shutdown_default_executor()`) and
`concurrent.futures`' atexit hook then JOIN that thread at teardown, so a single
timed-out call pins the whole Celery worker child for however long the abandoned
work actually takes — long past the timeout that was supposed to bound it, and
long past the task's own soft time limit.

A plain daemon thread is never joined by either, so a timeout here really does
abandon the work and the task returns on schedule. The cost is that the orphaned
call keeps burning CPU until it finishes; callers must therefore treat a timeout
as terminal for that piece of work rather than immediately retrying it.
"""
import asyncio
import threading
from typing import Any, Callable


def run_in_daemon_thread(
    fn: Callable[..., Any], *args: Any, name: str = "blocking-call"
) -> "asyncio.Future[Any]":
    """Start `fn(*args)` on a daemon thread; return a Future carrying its result.

    The future is safe to abandon (cancel it, or let `wait_for` time it out):
    nothing joins the thread and its eventual result is simply discarded.
    """
    loop = asyncio.get_running_loop()
    future: "asyncio.Future[Any]" = loop.create_future()

    def _settle(setter: Callable[[Any], None], value: Any) -> None:
        # The awaiter may have given up (cancelled) while `fn` was still running.
        if not future.done():
            setter(value)

    def _publish(setter: Callable[[Any], None], value: Any) -> None:
        try:
            loop.call_soon_threadsafe(_settle, setter, value)
        except RuntimeError:
            # Loop already closed — nobody is waiting on this any more.
            pass

    def _target() -> None:
        try:
            result = fn(*args)
        except BaseException as exc:  # relayed verbatim to the awaiter
            _publish(future.set_exception, exc)
        else:
            _publish(future.set_result, result)

    threading.Thread(target=_target, name=name, daemon=True).start()
    return future


async def call_with_timeout(
    fn: Callable[..., Any], *args: Any, timeout: float, name: str = "blocking-call"
) -> Any:
    """`fn(*args)` on a daemon thread, raising TimeoutError if it outlasts `timeout`."""
    return await asyncio.wait_for(
        run_in_daemon_thread(fn, *args, name=name), timeout=timeout
    )
