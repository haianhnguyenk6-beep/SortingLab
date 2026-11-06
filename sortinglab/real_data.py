"""Import numeric columns from a locally downloaded Kaggle CSV and benchmark sorting."""
import argparse
import csv
import json
from pathlib import Path
from .algorithms import ALGORITHMS
from .benchmark import timed, memory_peak


def load_numeric(path, column, limit=2000):
    if not 1 <= limit <= 100000:
        raise ValueError("limit must be between 1 and 100000")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError(f"Column {column!r} not found. Available: {reader.fieldnames}")
        values = []
        for row in reader:
            raw = (row.get(column) or "").strip().replace(",", "")
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            if value != value or abs(value) == float("inf"):
                continue
            values.append(value)
            if len(values) >= limit:
                break
    if not values:
        raise ValueError("No valid numeric values in selected column")
    return values


def benchmark_csv(source, column, out, limit=2000, repeats=3):
    data = load_numeric(source, column, limit)
    if repeats < 2:
        raise ValueError("repeats must be >= 2")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    expected = sorted(data)
    for name, algorithm in ALGORITHMS.items():
        base = dict(dataset=Path(source).name, column=column,
                    algorithm=name, n=len(data))
        if name == "insertion" and len(data) > 10000:
            results.append(dict(**base, median_ms="", peak_kb="",
                                status="skipped", reason="quadratic_cap_10000"))
            continue
        try:
            if algorithm(data) != expected:
                raise AssertionError("Incorrect sorting output")
            samples, _ = timed(algorithm, data, repeats=repeats)
            import statistics
            peak = (None if name == "insertion" and len(data) > 4000
                    else memory_peak(algorithm, data))
            results.append(dict(
                **base, median_ms=round(statistics.median(samples), 6),
                peak_kb=(round(peak, 3) if peak is not None else ""),
                status="ok", reason="",
            ))
        except Exception as exc:
            results.append(dict(**base, median_ms="", peak_kb="",
                                status="error", reason=str(exc)))
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "dataset", "column", "algorithm", "n", "median_ms",
            "peak_kb", "status", "reason",
        ])
        writer.writeheader()
        writer.writerows(results)
    return results


def main():
    p = argparse.ArgumentParser(description="Benchmark a numeric column in a local Kaggle CSV")
    p.add_argument("--csv", required=True)
    p.add_argument("--column", required=True)
    p.add_argument("--out", default="results/kaggle/powerbi_sorting.csv")
    p.add_argument("--limit", type=int, default=2000)
    p.add_argument("--repeats", type=int, default=3)
    a = p.parse_args()
    print(json.dumps(benchmark_csv(a.csv, a.column, a.out, a.limit, a.repeats), indent=2))


if __name__ == "__main__":
    main()
