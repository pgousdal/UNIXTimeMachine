from __future__ import annotations

import os
from pathlib import Path


def process_start_ticks(pid: int | None) -> int | None:
    if not isinstance(pid, int) or pid <= 0:
        return None
    try:
        # The comm field may contain spaces and parentheses; fields after its final ')' are stable.
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def process_matches(pid: int | None, start_ticks: int | None) -> bool:
    actual = process_start_ticks(pid)
    return actual is not None and start_ticks is not None and actual == start_ticks


def process_exists(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
