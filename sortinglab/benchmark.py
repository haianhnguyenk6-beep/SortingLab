"""Fair timing, separate counters/memory, portable process timeout and CSV."""
import csv
import gc
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .algorithms import ALGORITHMS
from .data_generator import DISTRIBUTIONS, generate
from .instrumented import count_sort

FIELDS = ["experiment", "algorithm", "distribution", "n", "run", "time_ms",
          "comparisons", "moves", "peak_kb", "seed", "status", "reason",
          "batch", "input_sha256"]


def skip_reason(name: str, dist: str, n: int) -> str:
    """Conservative caps apply equally to timing/count/memory experiments."""
    if name == "insertion" and dist != "sorted" and n > 4000:
        return "quadratic_cap_4000"
    if name == "quick_last" and dist in ("sorted", "reversed") and n > 4000:
        return "quadratic_cap_4000"
    if name in ("quick_last", "quick_mo3") and dist == "few_unique" and n > 4000:
        return "duplicate_partition_cap_4000"
    return ""


def timed(fn: Callable, data: list, repeats: int = 7,
          batch_target: float = 0.015) -> tuple[list[float], int]:
    """Time public API including its copy, excluding generation/validation.

    Warm-up calibrates batch length. Each returned observation is milliseconds
    per call averaged over a batch; inputs stay alive and unchanged throughout.
    Output deletion is part of public-call lifecycle. GC state is restored.
    """
    if repeats < 2 or batch_target < 0:
        raise ValueError("repeats >= 2 and batch_target >= 0 required")
    expected = sorted(data)
    start = time.perf_counter()
    actual = fn(data)
    warm = time.perf_counter() - start
    if actual != expected:
        raise AssertionError("Incorrect warm-up output")
    batch = max(1, min(10000, math.ceil(batch_target / max(warm, 1e-9))))
    samples = []
    enabled = gc.isenabled()
    try:
        gc.disable()
        for _ in range(repeats):
            start = time.perf_counter()
            for _ in range(batch):
                fn(data)
            samples.append((time.perf_counter() - start) * 1000 / batch)
    finally:
        if enabled:
            gc.enable()
    return samples, batch


def memory_peak(fn: Callable, data: list) -> float:
    """Peak traced allocations in KiB, including output and auxiliary lists."""
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc is already active")
    tracemalloc.start()
    try:
        result = fn(data)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    if result != sorted(data):
        raise AssertionError("Incorrect memory-run output")
    return peak / 1024


def measure(name: str, dist: str, n: int, seed: int, repeats: int,
            experiment: str = "E1E2", detail: bool = True) -> list[dict]:
    """Measure a configuration; skipped cells are explicit rows."""
    if name not in ALGORITHMS or dist not in DISTRIBUTIONS:
        raise ValueError("Unknown algorithm or distribution")
    data = generate(n, dist, seed)
    digest = hashlib.sha256(json.dumps(data).encode()).hexdigest()
    base = dict(experiment=experiment, algorithm=name, distribution=dist,
                n=n, seed=seed, input_sha256=digest)
    reason = skip_reason(name, dist, n)
    if reason:
        return [dict(base, run=0, status="skipped", reason=reason)]
    samples, batch = timed(ALGORITHMS[name], data, repeats)
    comparisons = moves = peak = None
    if detail:
        output, comparisons, moves = count_sort(name, data)
        if output != sorted(data):
            raise AssertionError("Incorrect counted output")
        peak = memory_peak(ALGORITHMS[name], data)
    return [dict(base, run=i + 1, time_ms=value, comparisons=comparisons,
                 moves=moves, peak_kb=peak, batch=batch, status="ok", reason="")
            for i, value in enumerate(samples)]


def _worker(connection, args: tuple) -> None:
    try:
        connection.send(("ok", measure(*args)))
    except Exception as exc:
        connection.send(("error", repr(exc)))
    finally:
        connection.close()


def isolated(args: tuple, timeout: float = 45) -> list[dict]:
    """Bound a whole configuration in a spawned process (Windows/Linux)."""
    ctx = mp.get_context("spawn")
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(send, args))
    process.start()
    send.close()
    try:
        if receive.poll(timeout):
            try:
                status, result = receive.recv()
            except (EOFError, OSError) as exc:
                exitcode = process.exitcode
                raise RuntimeError(
                    f"Worker exited without a result (exit code {exitcode})"
                ) from exc
            if status == "error":
                raise RuntimeError(result)
            return result
        name, dist, n, seed, _, experiment, *_ = args
        return [dict(algorithm=name, distribution=dist, n=n, seed=seed,
                     experiment=experiment, run=0, status="timeout",
                     reason=f"configuration_timeout_{timeout}s")]
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receive.close()


def write_csv(path: Path, rows: list[dict], fields: list | None = None) -> None:
    """Write machine-readable UTF-8 CSV with a stable column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    """Summarize batch observations, retaining skips and sample CV."""
    groups = {}
    for row in rows:
        key = tuple(row.get(k) for k in
                    ("experiment", "algorithm", "distribution", "n", "seed"))
        groups.setdefault(key, []).append(row)
    output = []
    for group in groups.values():
        base = {k: v for k, v in group[0].items()
                if k not in ("run", "time_ms", "batch")}
        values = [float(r["time_ms"]) for r in group if r["status"] == "ok"]
        if values:
            std = statistics.stdev(values) if len(values) > 1 else 0
            base.update(median_ms=statistics.median(values), min_ms=min(values),
                        std_ms=std, cv_pct=100 * std / statistics.mean(values),
                        repeats=len(values))
        output.append(base)
    return output


def metadata() -> dict:
    """Capture real environment and SHA256 of every measurement module."""
    root = Path(__file__).parent
    cpu = platform.processor() or "unavailable"
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    return dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                python=sys.version, os=platform.platform(), cpu=cpu,
                logical_cpus=os.cpu_count(), power_mode="not controlled",
                environment="container; shared host, scheduling not controlled",
                timer=time.get_clock_info("perf_counter")._asdict()
                if hasattr(time.get_clock_info("perf_counter"), "_asdict")
                else str(time.get_clock_info("perf_counter")),
                source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(root.glob("*.py"))})


def run_matrix(out: Path, sizes: list[int], repeats: int = 7,
               seed: int = 42, small: bool = True) -> None:
    """Run a randomized matrix sequentially to avoid parallel timing noise."""
    out.mkdir(parents=True, exist_ok=True)
    configurations = [(a, d, n, seed, repeats, "E1E2", True)
                      for n in sizes for d in DISTRIBUTIONS for a in ALGORITHMS]
    if small:
        configurations += [(a, "random", n, seed, repeats, "small", False)
                           for n in (8, 16, 32, 64, 128, 256)
                           for a in ALGORITHMS]
    random.Random(seed).shuffle(configurations)
    rows = []
    meta = metadata()
    meta.update(sizes=sizes, repeats=repeats, seed=seed,
                configurations=len(configurations), timeout_seconds=45)
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for i, cfg in enumerate(configurations):
        rows.extend(isolated(cfg))
        write_csv(out / "raw.csv", rows)
        print(f"{i + 1}/{len(configurations)} {cfg[:3]}", flush=True)
    summary = summarize(rows)
    fields = list(dict.fromkeys(k for r in summary for k in r))
    write_csv(out / "summary.csv", summary, fields)
    detail = [r for r in summary if r["experiment"] == "E1E2"]
    for filename, columns in [
        ("E3_counts.csv", ["algorithm", "distribution", "n", "seed",
                           "status", "reason", "comparisons", "moves"]),
        ("E4_memory.csv", ["algorithm", "distribution", "n", "seed",
                           "status", "reason", "peak_kb"]),
    ]:
        write_csv(out / filename,
                  [{k: r.get(k) for k in columns} for r in detail], columns)
