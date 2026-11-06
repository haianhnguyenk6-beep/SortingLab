"""Requirements FR01-FR12 and NFR01-NFR06: executable acceptance tests."""
import csv
import gc
import json
import random
import tracemalloc
from collections import Counter
from dataclasses import dataclass

import pytest
from hypothesis import given, settings, strategies as st

from sortinglab import benchmark as b
from sortinglab import cli
from sortinglab.algorithms import ALGORITHMS
from sortinglab.data_generator import DISTRIBUTIONS, generate
from sortinglab.instrumented import count_sort

CASES = [[], [1], [2, 1], [1, 2], [1, 1], [-3, 0, -1], [5, 2, 9, 1, 5, 6],
         list(range(100)), list(range(100, 0, -1)), [7] * 100,
         [i % 3 for i in range(100)], [10**50, -10**50, 0]]


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("data", CASES)
def test_algorithms(name, data):
    before = list(data)
    output = ALGORITHMS[name](data)
    assert output == sorted(data)
    assert data == before
    assert output is not data
    counted, comparisons, moves = count_sort(name, data)
    assert counted == output
    assert comparisons >= 0
    assert moves is None if name == "timsort" else moves >= 0


@settings(max_examples=1000, deadline=None, derandomize=True)
@given(st.lists(st.integers(-100000, 100000), max_size=90))
def test_properties(data):
    before = data[:]
    for name, fn in ALGORITHMS.items():
        output = fn(data)
        assert all(output[i] <= output[i + 1] for i in range(len(output) - 1))
        assert Counter(output) == Counter(data)
        assert data == before
        assert count_sort(name, data)[0] == output


@dataclass
class Record:
    key: int
    serial: int

    def __lt__(self, other):
        return self.key < other.key


@pytest.mark.parametrize("name", ["insertion", "merge", "timsort"])
def test_stability(name):
    data = [Record(i % 4, i) for i in range(60)]
    assert ALGORITHMS[name](data) == sorted(data, key=lambda r: r.key)
    assert count_sort(name, data)[0] == sorted(data, key=lambda r: r.key)


@pytest.mark.parametrize("name", ["quick_last", "quick_mo3", "heap"])
def test_unstable_counterexample(name):
    # Search a small deterministic family for a real witness, not an assumption.
    rng = random.Random(82)
    witnesses = []
    for _ in range(100):
        data = [Record(rng.randrange(3), i) for i in range(12)]
        if ALGORITHMS[name](data) != sorted(data, key=lambda r: r.key):
            witnesses.append(data)
    assert witnesses


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5, 16, 100])
def test_exact_counts(n):
    rev = list(range(n, 0, -1))
    quadratic = n * (n - 1) // 2
    assert count_sort("insertion", rev)[1:] == (quadratic, quadratic + max(n - 1, 0))
    assert count_sort("insertion", sorted(rev))[1:] == (max(n - 1, 0), max(n - 1, 0))
    assert count_sort("quick_last", sorted(rev))[1] == quadratic
    assert count_sort("quick_last", [1] * n)[1] == quadratic


@pytest.mark.parametrize("n", [2, 4, 8, 16, 32])
def test_merge_formula(n):
    import math
    _, comparisons, moves = count_sort("merge", list(range(n)))
    assert comparisons == n * int(math.log2(n)) // 2
    assert moves == 2 * n * int(math.log2(n))


def test_quick_deep():
    data = list(range(2500))
    assert ALGORITHMS["quick_last"](data) == data


@pytest.mark.parametrize("dist", DISTRIBUTIONS)
@pytest.mark.parametrize("n", [0, 1, 9, 100, 1000])
def test_generator(dist, n):
    state = random.getstate()
    a = generate(n, dist, 42)
    assert a == generate(n, dist, 42)
    assert len(a) == n
    assert random.getstate() == state
    if dist == "sorted":
        assert a == list(range(n))
    elif dist == "reversed":
        assert a == list(range(n - 1, -1, -1))
    elif dist == "nearly":
        assert sorted(a) == list(range(n))
        assert sum(i != x for i, x in enumerate(a)) <= 2 * (n // 100)
    elif dist == "few_unique":
        assert len(set(a)) <= 10
        assert all(0 <= x < 10 for x in a)
    else:
        assert all(-n <= x <= n for x in a)


@pytest.mark.parametrize("n", [-1, 1000001, True, 1.5])
def test_invalid_n(n):
    with pytest.raises(ValueError):
        generate(n, "random")


def test_invalid_names():
    with pytest.raises(ValueError):
        generate(3, "unknown")
    with pytest.raises(ValueError):
        count_sort("unknown", [])
    with pytest.raises(ValueError):
        b.measure("unknown", "random", 2, 42, 3)


@pytest.mark.parametrize("name,dist,n,skip", [
    ("insertion", "reversed", 8000, True),
    ("insertion", "sorted", 8000, False),
    ("quick_last", "sorted", 8000, True),
    ("quick_mo3", "few_unique", 8000, True),
    ("merge", "random", 8000, False),
])
def test_skip(name, dist, n, skip):
    assert bool(b.skip_reason(name, dist, n)) == skip


def test_timing_memory_cleanup():
    before = gc.isenabled()
    samples, batch = b.timed(sorted, [3, 1, 2], 3, 0.001)
    assert len(samples) == 3 and min(samples) > 0 and batch >= 1
    assert gc.isenabled() == before
    gc.disable()
    b.timed(sorted, [], 2, 0)
    assert not gc.isenabled()
    gc.enable()
    with pytest.raises(ValueError):
        b.timed(sorted, [], 1)
    with pytest.raises(AssertionError):
        b.timed(lambda a: a, [2, 1], 2)
    assert b.memory_peak(sorted, [2, 1]) > 0
    with pytest.raises(AssertionError):
        b.memory_peak(lambda a: a, [2, 1])
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    with pytest.raises(RuntimeError):
        b.memory_peak(sorted, [])
    tracemalloc.stop()
    calls = [0]

    def fail_after_warmup(a):
        calls[0] += 1
        if calls[0] > 1:
            raise RuntimeError("expected test failure")
        return sorted(a)

    with pytest.raises(RuntimeError):
        b.timed(fail_after_warmup, [2, 1], 2)
    assert gc.isenabled()


def test_measure_csv(tmp_path):
    rows = b.measure("merge", "random", 20, 42, 3)
    rows += b.measure("insertion", "reversed", 8000, 42, 3)
    summary = b.summarize(rows)
    assert summary[0]["repeats"] == 3
    assert summary[0]["median_ms"] >= summary[0]["min_ms"]
    assert summary[1]["status"] == "skipped"
    b.write_csv(tmp_path / "x.csv", rows)
    with (tmp_path / "x.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 4
    meta = b.metadata()
    assert meta["source_sha256"]["algorithms.py"]
    assert meta["python"] and meta["timestamp_utc"]


def test_isolation():
    args = ("merge", "random", 10, 42, 2, "test", False)
    assert b.isolated(args)[0]["status"] == "ok"
    assert b.isolated(args, timeout=0)[0]["status"] == "timeout"
    with pytest.raises(RuntimeError):
        b.isolated(("unknown", "random", 10, 42, 2, "test", False))


def test_matrix_and_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(b, "isolated", lambda cfg: b.measure(*cfg))
    monkeypatch.setattr(cli, "isolated", lambda cfg: b.measure(*cfg))
    # Use zero-duration calibration but retain real clock reads and real sorting.
    original = b.timed
    monkeypatch.setattr(b, "timed", lambda fn, data, repeats: original(fn, data, repeats, 0))
    b.run_matrix(tmp_path / "matrix", [8], 2, small=True)
    raw = list(csv.DictReader((tmp_path / "matrix/raw.csv").open()))
    assert len(raw) == (30 + 36) * 2
    assert (tmp_path / "matrix/E3_counts.csv").exists()
    assert json.loads((tmp_path / "matrix/metadata.json").read_text())["configurations"] == 66
    assert cli.main(["demo", "--n", "12", "--csv", str(tmp_path / "demo.csv")]) == 0
    assert "Sorted sample:" in capsys.readouterr().out
    assert cli.main(["demo", "--algorithm", "merge", "--n", "0"]) == 0
    assert cli.main(["demo", "--algorithm", "insertion", "--n", "8000"]) == 1
    import sortinglab.plots
    monkeypatch.setattr(sortinglab.plots, "make_plots", lambda _: None)
    monkeypatch.setattr(cli, "run_matrix", lambda *a, **k: None)
    assert cli.main(["run", "--profile", "smoke", "--out", str(tmp_path)]) == 0
    assert cli.main(["plots", "--results", str(tmp_path)]) == 0


@pytest.mark.parametrize("args", [
    ["demo", "--n", "-1"], ["demo", "--n", "1000001"],
    ["demo", "--n", "abc"], ["demo", "--algorithm", "bogus"],
    ["demo", "--distribution", "bogus"], ["run", "--repeats", "1"],
])
def test_cli_invalid(args):
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
