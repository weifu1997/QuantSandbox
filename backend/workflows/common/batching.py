from __future__ import annotations

from itertools import islice
from typing import Iterable, Iterator, Sequence, TypeVar

T = TypeVar("T")


def chunked(items: Sequence[T] | Iterable[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    iterator = iter(items)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch
