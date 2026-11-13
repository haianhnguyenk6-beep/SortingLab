"""Run report generation through its default and explicit CLI inputs."""
import csv

import pytest

from scripts.build_dashboard import main


def write_results(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            'dataset', 'algorithm', 'median_ms', 'peak_kb', 'n', 'status',
        ])
        writer.writeheader()
        writer.writerow(dict(dataset='orders.csv', algorithm='merge',
                             median_ms=1.2, peak_kb=16, n=100, status='ok'))


def test_default_report_uses_the_web_benchmark_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_results(tmp_path / 'results/powerbi/final_benchmark.csv')
    assert main([]) == 0
    report = tmp_path / 'results/powerbi/FINAL_DASHBOARD.html'
    text = report.read_text(encoding='utf-8')
    assert 'orders.csv' in text and '<td>merge</td>' in text


def test_explicit_csv_and_output_paths_still_work(tmp_path):
    source = tmp_path / 'input folder/custom.csv'
    write_results(source)
    output = tmp_path / 'reports/custom.html'
    assert main(['--csv', str(source), '--out', str(output)]) == 0
    assert 'orders.csv' in output.read_text(encoding='utf-8')


def test_missing_csv_explains_how_to_create_results(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert 'Real-life Data' in message and '--csv' in message
    assert 'Traceback' not in message


def test_wrong_csv_schema_is_reported_without_a_traceback(tmp_path, capsys):
    source = tmp_path / 'wrong.csv'
    source.write_text('Amount\n3\n1\n', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        main(['--csv', str(source), '--out', str(tmp_path / 'report.html')])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert 'algorithm' in message and 'status' in message
    assert 'Traceback' not in message
    assert not (tmp_path / 'report.html').exists()
