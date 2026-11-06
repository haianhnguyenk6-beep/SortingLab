"""Count key comparisons and array writes, outside runtime measurements.

One swap = two array writes. Ignore input copy, buffer initialization,
scalar assignments and index arithmetic. Timsort moves are unavailable.
"""
from dataclasses import dataclass
from typing import Any

from .algorithms import ALGORITHMS, _heap, _insertion, _merge, _quick


@dataclass
class Counts:
    """Counters shared by values, output and merge auxiliary array."""

    comparisons: int = 0
    moves: int = 0


class Key:
    """Wrap a value without changing its ordering."""

    def __init__(self, value: Any, counts: Counts):
        self.value = value
        self.counts = counts

    def __lt__(self, other: "Key") -> bool:
        self.counts.comparisons += 1
        return self.value < other.value


class CountedList(list):
    """Count only element writes by the sorting kernels."""

    def __init__(self, values: list, counts: Counts):
        super().__init__(values)
        self.counts = counts

    def __setitem__(self, index: int, value: Any) -> None:
        self.counts.moves += 1
        super().__setitem__(index, value)


def count_sort(name: str, data: list) -> tuple[list, int, int | None]:
    """Return output, comparisons and writes (None for C baseline)."""
    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {name}")
    counts = Counts()
    a = CountedList([Key(x, counts) for x in data], counts)
    if name == "insertion":
        _insertion(a)
    elif name == "merge":
        aux = CountedList([None] * len(a), counts)
        _merge(a, aux, 0, len(a))
    elif name.startswith("quick"):
        _quick(a, name == "quick_mo3")
    elif name == "heap":
        _heap(a)
    else:
        a = sorted(a)
    return ([x.value for x in a], counts.comparisons,
            None if name == "timsort" else counts.moves)
