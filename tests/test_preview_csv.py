"""Check the standalone preview's actual JavaScript against CSV export cases."""
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess

import pytest

NODE = shutil.which('node')
PREVIEW = Path(__file__).resolve().parents[1] / 'powerbi/SortingLab_Interactive_Dashboard.html'
pytestmark = pytest.mark.skipif(NODE is None, reason='Node.js is needed for preview tests')


def evaluate(expression):
    script = r'''
const fs = require('fs'), vm = require('vm');
const elements = {};
const document = {getElementById(id) {
  return elements[id] || (elements[id] = {innerHTML: '', textContent: ''});
}};
const html = fs.readFileSync(process.argv[1], 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({document});
vm.runInContext(source, context);
const expression = fs.readFileSync(0, 'utf8');
Promise.resolve(vm.runInContext(expression, context)).then(result => {
  console.log(JSON.stringify(result));
}).catch(error => { console.error(error); process.exitCode = 1; });
'''
    result = subprocess.run([NODE, '-e', script, str(PREVIEW)], input=expression,
                            text=True, encoding='utf-8', capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('value', [
    'orders,nov.csv', 'orders "special".csv', 'first\nsecond.csv',
    'first\r\nsecond.csv', 'dữ liệu.csv', '', '  orders.csv  ',
])
def test_quoted_export_fields_do_not_shift_algorithm_or_status(value):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['dataset', 'algorithm', 'median_ms', 'peak_kb', 'status', 'reason'])
    writer.writerow([value, 'merge', '1.2', '16', 'ok', ''])
    content = '\ufeff' + stream.getvalue()
    parsed = evaluate('parseCSV(' + json.dumps(content) + ')')
    assert parsed == [dict(dataset=value, algorithm='merge', median_ms='1.2',
                           peak_kb='16', status='ok', reason='')]


@pytest.mark.parametrize('content', [
    '', 'a,a\n1,2\n', 'a,b\n1\n', 'a\n"unfinished',
    'a\nun"quoted\n', 'a\n"done"unexpected\n',
])
def test_malformed_csv_has_an_error_instead_of_shifted_values(content):
    expression = ('(() => { try { parseCSV(' + json.dumps(content) + '); '
                  'return false; } catch (error) { return Boolean(error.message); } })()')
    assert evaluate(expression) is True


def test_empty_quoted_cell_and_blank_lines():
    assert evaluate('parseCSV(' + json.dumps('a\r\n""\r\n\r\nvalue') + ')') == [
        {'a': ''}, {'a': 'value'},
    ]


def test_render_excludes_missing_runtime_and_escapes_csv_labels():
    expression = r'''
(() => {
  rows = [
    {algorithm: '<img src=x>', median_ms: '1.2', peak_kb: '16', status: 'ok'},
    {algorithm: 'merge', median_ms: '', peak_kb: '', status: 'ok'},
    {algorithm: 'heap', median_ms: '-2', peak_kb: '', status: 'ok'},
    {algorithm: '<img src=x>', median_ms: '2', peak_kb: '', status: 'ok'}
  ];
  render();
  return {
    bars: document.getElementById('bars').innerHTML,
    table: document.getElementById('rows').innerHTML,
    kpis: document.getElementById('kpis').innerHTML
  };
})()
'''
    result = evaluate(expression)
    assert '<img src=x>' not in result['bars'] and '<img src=x>' not in result['table']
    assert '&lt;img src=x&gt;' in result['bars']
    assert 'merge' not in result['bars'] and 'heap' not in result['bars']
    assert 'Successful<div class="num">2</div>' in result['kpis']
    assert 'Algorithms<div class="num">3</div>' in result['kpis']
    assert 'Avg peak KB<div class="num">16.000</div>' in result['kpis']


def test_bad_upload_preserves_last_results_and_shows_error():
    expression = r'''
(async () => {
  const before = JSON.stringify(rows);
  await document.getElementById('csv').onchange({target: {files: [{
    name: 'broken.csv', text: async () => 'algorithm,status\n"unfinished'
  }]}});
  return {unchanged: before === JSON.stringify(rows),
    message: document.getElementById('csv-status').textContent};
})()
'''
    result = evaluate(expression)
    assert result['unchanged']
    assert result['message'].startswith('Không đọc được CSV:')


def test_valid_upload_retains_quoted_dataset_and_renders_results():
    expression = r'''
(async () => {
  await document.getElementById('csv').onchange({target: {files: [{
    name: 'results.csv', text: async () =>
      'dataset,algorithm,median_ms,peak_kb,status\r\n"orders,nov.csv",merge,1.2,16,ok\r\n'
  }]}});
  return {parsed: rows, bars: document.getElementById('bars').innerHTML,
    message: document.getElementById('csv-status').textContent};
})()
'''
    result = evaluate(expression)
    assert result['parsed'][0]['dataset'] == 'orders,nov.csv'
    assert result['parsed'][0]['status'] == 'ok'
    assert 'merge' in result['bars'] and '1.200' in result['bars']
    assert '1 bản ghi' in result['message']
