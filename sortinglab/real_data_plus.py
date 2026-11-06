"""Validated CSV ingestion, reproducible sorting benchmarks, and Power BI exports."""
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from .algorithms import ALGORITHMS
from .benchmark import timed, memory_peak

FIELDS = ['run_id', 'run_utc', 'dataset', 'sha256', 'column', 'algorithm', 'n',
          'repeats', 'median_ms', 'min_ms', 'max_ms', 'peak_kb', 'status', 'reason']


def numeric_columns(path, sample=100):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV header is missing')
        scores = {c: 0 for c in reader.fieldnames}
        for i, row in enumerate(reader):
            if i >= sample:
                break
            for c in scores:
                try:
                    v = float((row.get(c) or '').strip().replace(',', ''))
                    if math.isfinite(v):
                        scores[c] += 1
                except (ValueError, TypeError):
                    pass
        return [c for c in scores if scores[c] > 0]


def read_values(path, column, limit=2000):
    if not 1 <= limit <= 100000:
        raise ValueError('limit must be 1..100000')
    values = []
    ignored = 0
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            raise ValueError('Unknown column: ' + column)
        for row in reader:
            try:
                val = float((row.get(column) or '').strip().replace(',', ''))
                if not math.isfinite(val):
                    raise ValueError()
                values.append(val)
            except (ValueError, TypeError):
                ignored += 1
            if len(values) >= limit:
                break
    if not values:
        raise ValueError('No valid finite numeric values')
    return values, ignored


def run_csv(path, column, out='results/powerbi/sorting_benchmark_v2.csv', limit=2000, repeats=3):
    if not 2 <= repeats <= 30:
        raise ValueError('repeats must be 2..30')
    data, ignored = read_values(path, column, limit)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    run_id = hashlib.sha256((digest + column + stamp).encode()).hexdigest()[:12]
    expected = sorted(data)
    rows = []
    for name, algo in ALGORITHMS.items():
        record = dict(
            run_id=run_id, run_utc=stamp, dataset=Path(path).name,
            sha256=digest, column=column, algorithm=name,
            n=len(data), repeats=repeats, median_ms='', min_ms='',
            max_ms='', peak_kb='', status='ok', reason='',
        )
        if name == 'insertion' and len(data) > 10000:
            record.update(status='skipped', reason='quadratic_cap_10000')
        else:
            try:
                if algo(data) != expected:
                    raise AssertionError('Output mismatch')
                samples, _ = timed(algo, data, repeats=repeats)
                peak_kb = (
                    "" if name == "insertion" and len(data) > 4000
                    else round(memory_peak(algo, data), 3)
                )
                record.update(
                    median_ms=round(statistics.median(samples), 6),
                    min_ms=round(min(samples), 6),
                    max_ms=round(max(samples), 6),
                    peak_kb=peak_kb,
                )
                if name == "insertion" and len(data) > 4000:
                    record["reason"] = "memory_peak_not_measured_large_insertion"
            except Exception as exc:
                record.update(status='error', reason=str(exc))
        rows.append(record)
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        'source': str(path), 'sha256': digest,
        'selected_column': column, 'valid_rows': len(data),
        'invalid_rows_skipped': ignored, 'run_id': run_id,
        'created_utc': stamp,
    }
    output.with_suffix('.json').write_text(
        json.dumps(metadata, indent=2), encoding='utf-8'
    )
    return rows
