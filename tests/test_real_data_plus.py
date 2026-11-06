import csv
import pytest
from sortinglab.real_data_plus import numeric_columns, read_values, run_csv


def test_invalid_and_infinite(tmp_path):
    p = tmp_path / 'input.csv'
    p.write_text('sales,label\n10,a\nNaN,b\ninf,c\n20,d\ninvalid,e\n', encoding='utf-8')
    assert numeric_columns(p) == ['sales']
    assert read_values(p, 'sales') == ([10., 20.], 3)


def test_benchmark_export(tmp_path):
    p = tmp_path / 'orders.csv'
    p.write_text('amount\n4\n1\n3\n2\n', encoding='utf-8')
    output = tmp_path / 'results.csv'
    rows = run_csv(p, 'amount', output, repeats=2)
    assert len(rows) > 0 and all(r['status'] == 'ok' for r in rows)
    assert output.exists() and output.with_suffix('.json').exists()
    with output.open(encoding='utf-8-sig', newline='') as f:
        assert len(list(csv.DictReader(f))) == len(rows)


def test_validation(tmp_path):
    p = tmp_path / 'data.csv'
    p.write_text('v\n1\n')
    with pytest.raises(ValueError):
        run_csv(p, 'v', tmp_path / 'x.csv', repeats=1)
    with pytest.raises(ValueError):
        read_values(p, 'missing')
