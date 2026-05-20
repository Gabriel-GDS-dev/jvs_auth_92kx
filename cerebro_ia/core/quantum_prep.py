from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class QuantumPrep:
    """Small parallel executor used as the local prep layer for multi-context work."""

    def run_parallel(self, items: Iterable[T], fn: Callable[[T], R], max_workers: int = 4) -> list[R]:
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            return list(executor.map(fn, items))

