"""Import numeric columns from a locally downloaded Kaggle CSV and benchmark sorting."""
import argparse
import csv
import json
from pathlib import Path
from .algorithms import ALGORITHMS
from .csv_input import ensure_csv_data
from .real_data_plus import (
    CSV_TIMEOUT_SECONDS, csv_skip_reason, isolated_csv_measurement,
)


def load_numeric(path, column, limit=2000):
    if not 1 <= limit <= 100000:
        raise ValueError("limit must be between 1 and 100000")
    ensure_csv_data(path)
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


def benchmark_csv(source, column, out, limit=2000, repeats=3,
                  timeout=CSV_TIMEOUT_SECONDS):
    data = load_numeric(source, column, limit)
    if repeats < 2:
        raise ValueError("repeats must be >= 2")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for name in ALGORITHMS:
        base = dict(dataset=Path(source).name, column=column,
                    algorithm=name, n=len(data))
        reason = csv_skip_reason(name, data)
        if reason:
            results.append(dict(**base, median_ms="", peak_kb="",
                                status="skipped", reason=reason))
            continue
        measured = isolated_csv_measurement(name, data, repeats, timeout)
        results.append(dict(
            **base, median_ms=measured.get('median_ms', ''),
            peak_kb=measured.get('peak_kb', ''), status=measured['status'],
            reason=measured.get('reason', ''),
        ))
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
