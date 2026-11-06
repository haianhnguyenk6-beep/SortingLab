"""Non-mutating sort API; kernels also serve the separate counting run.

Objects need only __lt__. No key decoration is used in the timing experiment.
"""
from typing import Any, Callable, Iterable


def _swap(a: list, i: int, j: int) -> None:
    if i != j:
        a[i], a[j] = a[j], a[i]


def _insertion(a: list) -> None:
    for i in range(1, len(a)):
        value = a[i]
        j = i - 1
        while j >= 0 and value < a[j]:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = value


def _merge(a: list, aux: list, lo: int, hi: int) -> None:
    if hi - lo < 2:
        return
    mid = (lo + hi) // 2
    _merge(a, aux, lo, mid)
    _merge(a, aux, mid, hi)
    i, j = lo, mid
    for k in range(lo, hi):
        if i < mid and (j >= hi or not a[j] < a[i]):
            aux[k] = a[i]
            i += 1
        else:
            aux[k] = a[j]
            j += 1
    for k in range(lo, hi):
        a[k] = aux[k]


def _median_index(a: list, lo: int, hi: int) -> int:
    mid = (lo + hi) // 2
    if a[lo] < a[mid]:
        if a[mid] < a[hi]:
            return mid
        return hi if a[lo] < a[hi] else lo
    if a[lo] < a[hi]:
        return lo
    return hi if a[mid] < a[hi] else mid


def _quick(a: list, mo3: bool = False) -> None:
    # Process the smaller partition immediately; store only the larger one.
    # Pending stack is O(log n), even when partitioning costs Theta(n^2).
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            if mo3:
                _swap(a, _median_index(a, lo, hi), hi)
            pivot, i = a[hi], lo
            for j in range(lo, hi):
                if not pivot < a[j]:  # a[j] <= pivot, using only __lt__
                    _swap(a, i, j)
                    i += 1
            _swap(a, i, hi)
            left, right = (lo, i - 1), (i + 1, hi)
            if i - lo < hi - i:
                small, large = left, right
            else:
                small, large = right, left
            if large[0] < large[1]:
                stack.append(large)
            lo, hi = small


def _heap(a: list) -> None:
    def sift(root: int, end: int) -> None:
        while 2 * root + 1 < end:
            child = 2 * root + 1
            if child + 1 < end and a[child] < a[child + 1]:
                child += 1
            if not a[root] < a[child]:
                return
            _swap(a, root, child)
            root = child

    for root in range(len(a) // 2 - 1, -1, -1):
        sift(root, len(a))
    for end in range(len(a) - 1, 0, -1):
        _swap(a, 0, end)
        sift(0, end)


def insertion_sort(data: Iterable[Any]) -> list:
    """Return a stable sorted copy using insertion sort."""
    a = list(data)
    _insertion(a)
    return a


def merge_sort(data: Iterable[Any]) -> list:
    """Return a stable sorted copy using top-down merge sort."""
    a = list(data)
    _merge(a, [None] * len(a), 0, len(a))
    return a


def quick_sort_basic(data: Iterable[Any]) -> list:
    """Return a sorted copy using last-pivot Lomuto partitioning."""
    a = list(data)
    _quick(a)
    return a


def quick_sort_mo3(data: Iterable[Any]) -> list:
    """Return a sorted copy using median-of-three Lomuto partitioning."""
    a = list(data)
    _quick(a, True)
    return a


def heap_sort(data: Iterable[Any]) -> list:
    """Return a sorted copy using bottom-up max-heap construction."""
    a = list(data)
    _heap(a)
    return a


ALGORITHMS: dict[str, Callable] = {
    "insertion": insertion_sort,
    "merge": merge_sort,
    "quick_last": quick_sort_basic,
    "quick_mo3": quick_sort_mo3,
    "heap": heap_sort,
    "timsort": sorted,
}
