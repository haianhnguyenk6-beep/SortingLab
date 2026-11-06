"""HTTP regression coverage for data isolation, exports, and navigation changes."""
import csv
import hashlib
import io
import json
import re
import shutil
import threading
import zipfile
from http.client import HTTPConnection
from urllib.parse import urlencode

import pytest

from dashboard import server as app
from scripts.build_dashboard import build


@pytest.fixture
def http_app(tmp_path, monkeypatch):
    shutil.copytree(app.ROOT / 'dashboard', tmp_path / 'dashboard',
                    ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    monkeypatch.setattr(app, 'UPLOAD', tmp_path / 'uploads')
    monkeypatch.setattr(app, 'OUTPUT', tmp_path / 'latest.csv')
    monkeypatch.setattr(app, 'HISTORY', tmp_path / 'history.csv')
    monkeypatch.setattr(app, 'BATCH_OUTPUT', tmp_path / 'batch.csv')

    class QuietHandler(app.Handler):
        def log_message(self, *_args):
            pass

    server = app.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def request(method, route, body=None, headers=None):
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=40)
        connection.request(method, route, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    yield request
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def upload(request, filename, content):
    boundary = 'sortinglab-test-boundary'
    header = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="dataset"; filename="{filename}"\r\n'
        'Content-Type: text/csv\r\n\r\n'
    ).encode()
    body = header + content + f'\r\n--{boundary}--\r\n'.encode()
    return request('POST', '/upload', body,
                   {'Content-Type': f'multipart/form-data; boundary={boundary}'})


def post_form(request, route, **params):
    return request('POST', route, urlencode(params).encode(), {
                   'Content-Type': 'application/x-www-form-urlencoded'})


def test_two_uploads_keep_their_sources_and_export_correctly(http_app):
    first = b'Amount\n4\n1\n3\n2\n'
    second = b'Amount\n80\n70\n60\n'
    status, _, page_a = upload(http_app, 'orders-a.csv', first)
    assert status == 200
    status, _, page_b = upload(http_app, 'orders-b.csv', second)
    assert status == 200
    ref_a = re.search(rb'name="source" value="([^"]+)"', page_a)[1].decode()
    ref_b = re.search(rb'name="source" value="([^"]+)"', page_b)[1].decode()
    assert ref_a != ref_b
    # Submit the first tab after the second upload: it must still measure A.
    status, headers, _ = post_form(http_app, '/benchmark', source=ref_a, column='Amount', limit=100)
    assert status == 303 and headers['Location'] == '/powerbi'
    with app.HISTORY.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert {row['dataset'] for row in rows} == {'orders-a.csv'}
    assert {row['n'] for row in rows} == {'4'}
    assert {row['sha256'] for row in rows} == {hashlib.sha256(first).hexdigest()}
    assert all(row['status'] == 'ok' for row in rows)
    for route in ('/export', '/export-history', '/report', '/results?view=latest'):
        assert http_app('GET', route)[0] == 200
    status, headers, data = http_app('GET', '/export-excel')
    assert status == 200 and 'spreadsheetml' in headers['Content-Type']
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        assert b'orders-a.csv' in book.read('xl/worksheets/sheet1.xml')
        assert len(book.namelist()) == 6


def test_invalid_upload_and_traversal_do_not_change_valid_source(http_app):
    assert upload(http_app, 'valid.csv', b'value\n2\n1\n')[0] == 200
    sources = set(app.UPLOAD.rglob('*.csv'))
    assert upload(http_app, 'labels.csv', b'word\nhello\nworld\n')[0] == 400
    assert upload(http_app, 'fake.txt', b'v\n1\n')[0] == 400
    assert set(app.UPLOAD.rglob('*.csv')) == sources
    assert post_form(http_app, '/benchmark', source='../outside.csv',
                     column='value', limit=100)[0] == 400
    assert not app.HISTORY.exists()


def test_local_csv_flow_uses_explicit_source_and_real_filename(http_app, tmp_path, monkeypatch):
    local = tmp_path / 'SampleSuperstore.csv'
    local.write_text('Sales\n3\n1\n2\n', encoding='utf-8')
    monkeypatch.setattr(app, 'dataset_path', lambda key: local)
    status, _, page = post_form(http_app, '/use-local-kaggle', dataset='superstore')
    assert status == 200 and b'local:superstore' in page
    assert not app.UPLOAD.exists()
    status, _, _ = post_form(http_app, '/benchmark',
                             source='local:superstore', column='Sales', limit=100)
    assert status == 303
    with app.OUTPUT.open(encoding='utf-8-sig', newline='') as stream:
        assert {row['dataset'] for row in csv.DictReader(stream)} == {'SampleSuperstore.csv'}


def test_new_navigation_and_old_urls_remain_available(http_app):
    for route in ('/', '/real-data', '/batch', '/history', '/tools',
                  '/results?view=overview', '/results?view=compare',
                  '/results?view=explore', '/results?view=latest',
                  '/compare', '/insights', '/executive', '/powerbi',
                  '/quality', '/audit', '/validation', '/readiness',
                  '/powerbi-health', '/reproducibility', '/submission'):
        status, _, body = http_app('GET', route)
        assert status == 200, route
        assert b'{{BODY}}' not in body
        assert body.count(b'data-nav="real-data"') == 1
    assert http_app('GET', '/assets/app.css')[0] == 200
    assert http_app('GET', '/assets/../server.py')[0] == 404
    assert http_app('GET', '/results?view=unknown')[0] == 400


def test_experiment_api_and_live_measurement(http_app):
    status, _, payload = http_app('GET', '/api/overview')
    assert status == 200
    stats = json.loads(payload)
    assert stats['configurations'] == stats['measured'] + stats['skipped']
    assert len(stats['figures']) == 22 and stats['observations'] == 1728
    status, _, payload = http_app('GET', '/api/demo?n=100&distribution=random&seed=42')
    assert status == 200
    result = json.loads(payload)
    assert len(result['rows']) == 6
    assert all(row['status'] == 'ok' for row in result['rows'])
    assert result['first'] == sorted(result['first'])
    assert http_app('GET', '/api/demo?n=999999&distribution=random&seed=42')[0] == 400


def test_missing_memory_still_appears_in_report(tmp_path, monkeypatch):
    source = tmp_path / 'benchmark.csv'
    source.write_text(
        'algorithm,median_ms,peak_kb,n,dataset,status\n'
        'insertion,1.5,,5000,orders.csv,ok\n'
        'merge,2.2,18,5000,orders.csv,ok\n'
        'heap,nan,3,5000,orders.csv,ok\n',
        encoding='utf-8',
    )
    target = tmp_path / 'report.html'
    build(source, target)
    report = target.read_text(encoding='utf-8')
    assert 'insertion' in report and 'merge' in report
    assert '<td>—</td>' in report
    assert '<td>heap</td>' not in report
    monkeypatch.setattr(app, 'BATCH_OUTPUT', source)
    assert '<td>insertion</td>' in app.executive_report_page({})


def test_batch_reports_missing_sources_and_exports_measured_rows(http_app, tmp_path, monkeypatch):
    source = tmp_path / 'local.csv'
    source.write_text('Sales,price\n4,40\n1,10\n3,30\n2,20\n', encoding='utf-8')
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    monkeypatch.setattr(app, 'dataset_path', lambda key: tmp_path /
                        'missing.csv' if key == 'creditcard' else source)
    status, _, page = http_app('POST', '/batch-run', b'')
    assert status == 200 and b'creditcard' in page
    status, _, payload = http_app('GET', '/export-batch')
    assert status == 200
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    assert len(rows) == 36
    assert {row['dataset'] for row in rows} == {'superstore', 'olist'}
    assert {row['n'] for row in rows} == {'4'}
    assert all(row['status'] == 'ok' for row in rows)
    assert http_app('GET', '/export-batch-excel')[0] == 200
    status, _, payload = http_app('GET', '/export-executive?dataset=superstore')
    assert status == 200
    filtered = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    assert {row['dataset'] for row in filtered} == {'superstore'}


def test_another_tab_cannot_start_overlapping_measurements(http_app):
    with app.BENCHMARK_LOCK:
        status, _, payload = http_app('GET', '/api/demo?n=100&distribution=random&seed=42')
    assert status == 400
    assert 'đang chạy' in json.loads(payload)['error']
