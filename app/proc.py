"""Run CLI engines as cancellable async subprocesses.

Using asyncio subprocesses (instead of subprocess.run in a thread) lets a Stop
request actually kill the running `claude`/`codex` processes — both when the
request task is cancelled and via an explicit kill_all().
"""

from __future__ import annotations

import asyncio

_active: set[asyncio.subprocess.Process] = set()


async def run_capture(
    args: list[str],
    input_text: str | None = None,
    cwd: str | None = None,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr). Killed on cancel/timeout."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if input_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    _active.add(proc)
    try:
        data = input_text.encode() if input_text is not None else None
        out, err = await asyncio.wait_for(proc.communicate(data), timeout=timeout)
        return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")
    except (asyncio.CancelledError, asyncio.TimeoutError):
        _kill(proc)
        await asyncio.gather(proc.wait(), return_exceptions=True)
        raise
    finally:
        _active.discard(proc)


def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def kill_all() -> int:
    """Kill every active engine subprocess. Returns how many were killed."""
    procs = list(_active)
    for p in procs:
        _kill(p)
    return len(procs)
