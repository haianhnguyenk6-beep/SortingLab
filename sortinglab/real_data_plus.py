"""Validated CSV ingestion, reproducible sorting benchmarks, and Power BI exports."""
import csv
import hashlib
import json
import math
import multiprocessing as mp
import statistics
from datetime import datetime, timezone
from pathlib import Path
from .algorithms import ALGORITHMS
from .benchmark import timed, memory_peak
from .csv_input import ensure_csv_data

CSV_TIMEOUT_SECONDS = 15

FIELDS = ['run_id', 'run_utc', 'dataset', 'sha256', 'column', 'algorithm', 'n',
          'repeats', 'median_ms', 'min_ms', 'max_ms', 'peak_kb', 'status', 'reason']


def numeric_columns(path, sample=None):
    """Find finite numeric columns, including after leading missing values."""
    ensure_csv_data(path)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV header is missing')
        scores = {c: 0 for c in reader.fieldnames}
        for i, row in enumerate(reader):
            if sample is not None and i >= sample:
                break
            for c in scores:
                try:
                    v = float((row.get(c) or '').strip().replace(',', ''))
                    if math.isfinite(v):
                        scores[c] += 1
                except (ValueError, TypeError):
                    pass
            if all(scores.values()):
                break
        return [c for c in scores if scores[c] > 0]


def read_values(path, column, limit=2000):
    if not 1 <= limit <= 100000:
        raise ValueError('limit must be 1..100000')
    ensure_csv_data(path)
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


def _csv_measurement(name, data, repeats):
    algorithm = ALGORITHMS[name]
    if algorithm(data) != sorted(data):
        raise AssertionError('Output mismatch')
    samples, _ = timed(algorithm, data, repeats=repeats)
    omit_memory = name == 'insertion' and len(data) > 4000
    return dict(
        median_ms=round(statistics.median(samples), 6),
        min_ms=round(min(samples), 6), max_ms=round(max(samples), 6),
        peak_kb='' if omit_memory else round(memory_peak(algorithm, data), 3),
        reason='memory_peak_not_measured_large_insertion' if omit_memory else '',
    )


def _csv_worker(connection, name, data, repeats):
    try:
        connection.send(dict(status='ok', **_csv_measurement(name, data, repeats)))
    except Exception as exc:
        connection.send(dict(status='error', reason=str(exc)))
    finally:
        connection.close()


def isolated_csv_measurement(name, data, repeats, timeout):
    """Bound validation, timing and memory together in a portable child process."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be a finite positive number')
    context = mp.get_context('spawn')
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_csv_worker, args=(send, name, data, repeats))
    process.start()
    send.close()
    try:
        if receive.poll(timeout):
            try:
                return receive.recv()
            except (EOFError, OSError):
                return dict(status='error', reason='Benchmark worker exited without a result')
        return dict(status='timeout', reason=f'configuration_timeout_{timeout}s')
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receive.close()


def csv_skip_reason(name, data):
    if len(data) <= 4000:
        return ''
    ascending = all(left <= right for left, right in zip(data, data[1:]))
    if name == 'insertion' and not ascending:
        return 'quadratic_cap_4000'
    if name == 'quick_last' and (
        ascending or all(left >= right for left, right in zip(data, data[1:]))
    ):
        return 'quadratic_cap_4000'
    if name in ('quick_last', 'quick_mo3') and len(set(data)) <= 10:
        return 'duplicate_partition_cap_4000'
    return ''


def run_csv(path, column, out='results/powerbi/sorting_benchmark_v2.csv',
            limit=2000, repeats=3, timeout=CSV_TIMEOUT_SECONDS):
    if not 2 <= repeats <= 30:
        raise ValueError('repeats must be 2..30')
    data, ignored = read_values(path, column, limit)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be a finite positive number')
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    run_id = hashlib.sha256((digest + column + stamp).encode()).hexdigest()[:12]
    rows = []
    for name in ALGORITHMS:
        record = dict(
            run_id=run_id, run_utc=stamp, dataset=Path(path).name,
            sha256=digest, column=column, algorithm=name,
            n=len(data), repeats=repeats, median_ms='', min_ms='',
            max_ms='', peak_kb='', status='ok', reason='',
        )
        reason = csv_skip_reason(name, data)
        if reason:
            record.update(status='skipped', reason=reason)
        else:
            record.update(isolated_csv_measurement(name, data, repeats, timeout))
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
