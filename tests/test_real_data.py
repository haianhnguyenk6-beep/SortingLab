import csv
import pytest
from sortinglab.real_data import load_numeric, benchmark_csv


def test_load_numeric_filters_bad_values(tmp_path):
    source = tmp_path / 'sales.csv'
    with source.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Sales'])
        w.writerows([['10.5'], ['bad'], [''], ['3'], ['NaN']])
    assert load_numeric(source, 'Sales') == [10.5, 3.0]


def test_benchmark_export(tmp_path):
    source = tmp_path / 'data.csv'
    source.write_text('Sales\n8\n3\n9\n1\n', encoding='utf-8')
    target = tmp_path / 'benchmark.csv'
    results = benchmark_csv(source, 'Sales', target, limit=4, repeats=2)
    assert target.exists()
    assert results and all(r['status'] == 'ok' for r in results)


def test_missing_column(tmp_path):
    source = tmp_path / 'data.csv'
    source.write_text('Sales\n12\n', encoding='utf-8')
    with pytest.raises(ValueError, match='not found'):
        load_numeric(source, 'Price')
