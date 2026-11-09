"""Regression tests for missing LFS data, sparse CSVs and bounded measurement."""
import csv
import multiprocessing as mp
import time
import tracemalloc
import zipfile

import pytest

from dashboard import server as app
from scripts import kaggle_pipeline
from sortinglab import real_data_plus as real
from sortinglab.csv_input import is_lfs_pointer
from sortinglab.real_data import load_numeric, benchmark_csv

POINTER = ('version https://git-lfs.github.com/spec/v1\n'
           'oid sha256:' + 'a' * 64 + '\nsize 123456\n')


def test_lfs_placeholders_are_not_available_datasets(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    for name in ('OUTPUT', 'BATCH_OUTPUT', 'HISTORY'):
        monkeypatch.setattr(app, name, tmp_path / (name.lower() + '.csv'))
    for key, cfg in app.DATASETS.items():
        path = tmp_path / 'data' / 'kaggle' / key / cfg['file']
        path.parent.mkdir(parents=True)
        path.write_text(POINTER)
        assert is_lfs_pointer(path)
        for read in (real.numeric_columns,
                     lambda p: real.read_values(p, cfg['column']),
                     lambda p: load_numeric(p, cfg['column'])):
            with pytest.raises(ValueError, match='git lfs pull'):
                read(path)
    assert all(not ready for _, _, ready in app.dataset_choices())
    assert all(row['status'] == 'MISSING' for row in app.readiness_report()[:3])
    assert all('Git LFS' in row['error'] for row in app.dataset_quality_report())
    assert all(not row['present'] for row in
               app.reproducibility_manifest()['dataset_inventory'])


def test_dataset_readiness_checks_values_and_required_column(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    for key, content in [('superstore', 'Other\n1\n'), ('olist', 'price\nNaN\n')]:
        source = app.dataset_path(key)
        source.parent.mkdir(parents=True)
        source.write_text(content)
        assert app.dataset_state(key)[0] == 'INVALID'
    assert app.dataset_state('creditcard')[0] == 'MISSING'
    source = app.dataset_path('superstore')
    source.write_text('Sales\n3\n1\n')
    assert app.dataset_state('superstore')[0] == 'READY'


def test_numeric_columns_after_one_hundred_missing_rows(tmp_path):
    source = tmp_path / 'sparse.csv'
    source.write_text('Amount,Label\n' + ',empty\n' * 100 + '7,x\n3,y\n')
    assert real.numeric_columns(source) == ['Amount']
    assert real.numeric_columns(source, sample=100) == []
    assert real.read_values(source, 'Amount') == ([7.0, 3.0], 100)
    assert 'name="column"' in app.selection_form(source, 'Sparse data').decode()


@pytest.mark.parametrize('name,data,skipped', [
    ('insertion', list(range(5000)), False),
    ('insertion', list(range(5000))[::-1], True),
    ('quick_last', list(range(5000)), True),
    ('quick_last', list(range(5000))[::-1], True),
    ('quick_last', [i % 2 for i in range(5000)], True),
    ('quick_mo3', [i % 2 for i in range(5000)], True),
    ('merge', list(range(5000)), False),
])
def test_large_csv_quadratic_cases_are_skipped(name, data, skipped):
    assert bool(real.csv_skip_reason(name, data)) is skipped


def test_large_duplicate_csv_completes_and_retains_skip_reasons(tmp_path):
    source = tmp_path / 'duplicates.csv'
    source.write_text('Amount\n' + '1\n' * 50000)
    output = tmp_path / 'results.csv'
    rows = real.run_csv(source, 'Amount', output, limit=50000, repeats=2)
    skipped = {r['algorithm'] for r in rows if r['status'] == 'skipped'}
    assert skipped == {'quick_last', 'quick_mo3'}
    assert all(r['status'] in ('ok', 'skipped') for r in rows)
    assert all(r['reason'] for r in rows if r['status'] == 'skipped')
    with output.open(encoding='utf-8-sig', newline='') as stream:
        assert len(list(csv.DictReader(stream))) == 6


def test_timeout_terminates_worker_and_a_later_measurement_succeeds():
    children = {p.pid for p in mp.active_children()}
    start = time.monotonic()
    result = real.isolated_csv_measurement('quick_last', list(range(50000)), 2, 0.05)
    assert result['status'] == 'timeout'
    assert time.monotonic() - start < 5
    assert {p.pid for p in mp.active_children()} == children
    assert not tracemalloc.is_tracing()
    later = real.isolated_csv_measurement('merge', [3, 1, 2], 2, 15)
    assert later['status'] == 'ok' and later['peak_kb'] > 0
    assert real.isolated_csv_measurement('unknown', [2, 1], 2, 15)['status'] == 'error'


def test_measurements_validate_outputs_and_omit_slow_memory_run(monkeypatch):
    result = real._csv_measurement('merge', [3, 1, 2], 2)
    assert result['min_ms'] <= result['median_ms'] <= result['max_ms']
    assert result['peak_kb'] > 0
    large = real._csv_measurement('insertion', list(range(5000)), 2)
    assert large['peak_kb'] == '' and 'not_measured' in large['reason']
    monkeypatch.setitem(real.ALGORITHMS, 'broken', lambda values: values)
    with pytest.raises(AssertionError, match='Output mismatch'):
        real._csv_measurement('broken', [2, 1], 2)


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan')])
def test_invalid_measurement_timeouts(tmp_path, timeout):
    source = tmp_path / 'input.csv'
    source.write_text('Amount\n2\n1\n')
    with pytest.raises(ValueError, match='timeout'):
        real.run_csv(source, 'Amount', tmp_path / 'out.csv', timeout=timeout)
    with pytest.raises(ValueError, match='timeout'):
        real.isolated_csv_measurement('merge', [2, 1], 2, timeout)


def test_legacy_csv_export_also_records_timeouts(tmp_path):
    source = tmp_path / 'input.csv'
    source.write_text('Amount\n2\n1\n')
    rows = benchmark_csv(source, 'Amount', tmp_path / 'out.csv', timeout=0.000001)
    assert len(rows) == 6 and all(r['status'] == 'timeout' for r in rows)


def test_kaggle_download_replaces_existing_lfs_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(kaggle_pipeline, '__file__', str(tmp_path / 'scripts' / 'pipeline.py'))
    folder = tmp_path / 'data' / 'kaggle' / 'superstore'
    folder.mkdir(parents=True)
    source = folder / 'SampleSuperstore.csv'
    source.write_text(POINTER)

    def download(command, check):
        assert check and 'xubao666/superstore' in command
        with zipfile.ZipFile(folder / 'download.zip', 'w') as archive:
            archive.writestr('SampleSuperstore.csv', 'Sales\n3\n1\n2\n')

    monkeypatch.setattr(kaggle_pipeline.subprocess, 'run', download)
    monkeypatch.setattr(kaggle_pipeline.sys, 'argv', ['pipeline', '--download', '--repeats', '2'])
    kaggle_pipeline.main()
    assert not is_lfs_pointer(source)
    assert (tmp_path / 'results' / 'powerbi' / 'superstore_benchmark.csv').is_file()
