"""Ограниченный асинхронный запуск доверенного локального EDA-инструмента."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

MAX_LOG_BYTES = 65_536


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    duration_ms: int
    timed_out: bool


async def _collect(reader: asyncio.StreamReader | None, limit: int) -> tuple[str, bool]:
    if reader is None:
        return "", False
    data = bytearray()
    truncated = False
    while chunk := await reader.read(8192):
        room = limit - len(data)
        if room > 0:
            data.extend(chunk[:room])
        if len(chunk) > room:
            truncated = True
    return data.decode("utf-8", errors="replace"), truncated


async def _terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Принудительное завершение изолированной группы дочерних процессов."""
    if proc.returncode is not None:
        return
    if os.name == "nt":
        # taskkill /T завершает потомков (proc.kill() один этого не делает).
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        if taskkill.is_file():
            try:
                killer = await asyncio.create_subprocess_exec(
                    str(taskkill), "/F", "/T", "/PID", str(proc.pid),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), 3)
            except (OSError, asyncio.TimeoutError):
                pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), 5)
    except asyncio.TimeoutError:
        pass


async def run_bounded(
    argv: Sequence[str],
    cwd: Path,
    timeout_seconds: int,
    *,
    max_log_bytes: int = MAX_LOG_BYTES,
) -> ProcessResult:
    """Выполнить фиксированный argv без оболочки и с лимитом памяти журналов.

    Функция намеренно не публикуется как MCP tool и не принимает свободную
    командную строку от MCP-клиента.
    """
    if not argv or not 1 <= timeout_seconds <= 600:
        raise ValueError("Некорректный внутренний запрос запуска")
    flags = {}
    if os.name == "nt":
        flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        flags["start_new_session"] = True
    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **flags,
    )
    capture_out = asyncio.create_task(_collect(proc.stdout, max_log_bytes))
    capture_err = asyncio.create_task(_collect(proc.stderr, max_log_bytes))
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout_seconds)
    except asyncio.TimeoutError:
        timed_out = True
        await _terminate_process_tree(proc)
    except asyncio.CancelledError:
        await _terminate_process_tree(proc)
        capture_out.cancel()
        capture_err.cancel()
        await asyncio.gather(capture_out, capture_err, return_exceptions=True)
        raise
    # Даже после завершения процесса унаследованные pipe-объекты могут
    # оставаться открытыми у потомков: ограничиваем ожидание и здесь.
    try:
        (stdout, stdout_cut), (stderr, stderr_cut) = await asyncio.wait_for(
            asyncio.gather(capture_out, capture_err), 5
        )
    except asyncio.TimeoutError:
        timed_out = True
        await _terminate_process_tree(proc)
        capture_out.cancel()
        capture_err.cancel()
        await asyncio.gather(capture_out, capture_err, return_exceptions=True)
        stdout, stderr, stdout_cut, stderr_cut = "", "", True, True
    elapsed = round((time.monotonic() - start) * 1000)
    return ProcessResult(
        exit_code=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_cut,
        stderr_truncated=stderr_cut,
        duration_ms=elapsed,
        timed_out=timed_out,
    )
