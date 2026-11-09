"""Local, offline dashboard backed by the measured CSV and real sort kernels."""
import csv
import uuid
from contextlib import contextmanager
import hashlib
import platform
from datetime import datetime, timezone
import os
import io
from email.parser import BytesParser
from email.policy import default
import html
import json
import mimetypes
import subprocess
import sys
import shutil
import zipfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode

from dashboard.ui import render_page
from dashboard.views import real_data_body, batch_body, selection_body, latest_body, tools_body
from sortinglab.real_data_plus import run_csv, numeric_columns, read_values
from sortinglab.csv_input import ensure_csv_data, is_lfs_pointer
from scripts.build_dashboard import build
from sortinglab.algorithms import ALGORITHMS
from sortinglab.benchmark import isolated, summarize
from sortinglab.data_generator import DISTRIBUTIONS, generate

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "final" / "summary.csv"
FIGURES = ROOT / "results" / "final" / "figures"
PAGE = ROOT / "dashboard" / "index.html"
OUTPUT = ROOT / "results" / "powerbi" / "final_benchmark.csv"
UPLOAD = ROOT / "data" / "uploads"
MAX_UPLOAD = 12 * 1024 * 1024  # Browser uploads; local Kaggle files are not size-limited
HISTORY = ROOT / "results" / "powerbi" / "history.csv"
HISTORY_FIELDS = ["run_id","run_utc","dataset","sha256","column","algorithm","n","repeats","median_ms","min_ms","max_ms","peak_kb","status","reason"]
BENCHMARK_LOCK = threading.Lock()
DATASETS = {
    'superstore': {'slug':'xubao666/superstore','file':'SampleSuperstore.csv','column':'Sales','title':'Superstore Sales (Kaggle CSV)'},
    'olist': {'slug':'olistbr/brazilian-ecommerce','file':'olist_order_items_dataset.csv','column':'price','title':'Brazilian E-Commerce (Olist, Kaggle CSV)'},
    'creditcard': {'slug':'mlg-ulb/creditcardfraud','file':'creditcard.csv','column':'Amount','title':'Credit Card Fraud Detection (Kaggle CSV)'},
}
def dataset_path(key):
    if key not in DATASETS: raise ValueError('Dataset không hợp lệ')
    folder = ROOT / 'data' / 'kaggle' / key
    expected = folder / DATASETS[key]['file']
    if expected.is_file(): return expected
    matches = [f for f in folder.glob('*.csv') if f.name.lower() == DATASETS[key]['file'].lower()]
    return matches[0] if matches else expected


def dataset_state(key):
    """Check actual numeric data instead of the existence of a CSV filename."""
    source = dataset_path(key)
    if not source.is_file():
        return 'MISSING', 'Thiếu CSV gốc. Tải từ Kaggle hoặc chạy git lfs pull.'
    pointer = False
    try:
        pointer = is_lfs_pointer(source)
        read_values(source, DATASETS[key]['column'], limit=1)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        status = 'MISSING' if pointer else 'INVALID'
        return status, str(exc)
    return 'READY', str(source.relative_to(ROOT))


def dataset_choices():
    choices = []
    for key, cfg in DATASETS.items():
        status, detail = dataset_state(key)
        choices.append((key, dict(cfg, problem='' if status == 'READY' else detail),
                        status == 'READY'))
    return choices


@contextmanager
def benchmark_session():
    """Avoid concurrent tracemalloc sessions and writes from separate tabs."""
    if not BENCHMARK_LOCK.acquire(blocking=False):
        raise ValueError('Một benchmark đang chạy. Vui lòng chờ hoàn tất rồi thử lại.')
    try:
        yield
    finally:
        BENCHMARK_LOCK.release()


BATCH_OUTPUT = ROOT / "results" / "powerbi" / "all_datasets_benchmark.csv"
BATCH_SIZES = (1000, 5000, 10000)

# Native Excel workbook without third-party dependencies; Power BI can import .xlsx directly.
def benchmark_excel_bytes(source):
    from xml.sax.saxutils import escape as xml_escape
    import math
    if not source.is_file():
        raise ValueError('Chưa có kết quả benchmark. Hãy chạy Benchmark All trước.')
    with source.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        if not headers:
            raise ValueError('CSV benchmark không có tiêu đề cột')
        records = list(reader)
    if len(records) > 1048575:
        raise ValueError('Quá giới hạn số dòng của Excel')
    numeric_columns = {'n', 'repeats', 'median_ms', 'min_ms', 'max_ms', 'peak_kb'}
    def col_name(index):
        out = ''
        while index:
            index, rem = divmod(index - 1, 26)
            out = chr(65 + rem) + out
        return out
    def cell(ref, value, numeric=False, header=False):
        value = str(value if value is not None else '')
        if numeric and value.strip():
            try:
                number = float(value)
                if math.isfinite(number):
                    return f'<c r="{ref}" s="{2 if header else 0}"><v>{value}</v></c>'
            except ValueError:
                pass
        # Excel must not interpret arbitrary CSV text as formulas.
        return f'<c r="{ref}" t="inlineStr" s="{1 if header else 0}"><is><t>{xml_escape(value)}</t></is></c>'
    lines = []
    lines.append('<row r="1">'+''.join(cell(f'{col_name(i)}1', name, header=True) for i,name in enumerate(headers,1))+'</row>')
    for row_num, row in enumerate(records, 2):
        lines.append(f'<row r="{row_num}">'+''.join(cell(f'{col_name(i)}{row_num}',row.get(name,''),numeric=name in numeric_columns) for i,name in enumerate(headers,1))+'</row>')
    last_col = col_name(len(headers))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="16"/><cols>'
        + ''.join(f'<col min="{i}" max="{i}" width="{30 if name in ("run_utc","sha256","reason") else 19}" customWidth="1"/>' for i,name in enumerate(headers,1))
        + '</cols><sheetData>'+''.join(lines)+'</sheetData>'
        + f'<autoFilter ref="A1:{last_col}{len(records)+1}"/></worksheet>')
    content_types = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>')
    styles = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Aptos"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0D3848"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as book:
        book.writestr('[Content_Types].xml', content_types)
        book.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        book.writestr('xl/workbook.xml', '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Benchmark" sheetId="1" r:id="rId1"/></sheets></workbook>')
        book.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        book.writestr('xl/worksheets/sheet1.xml', sheet)
        book.writestr('xl/styles.xml', styles)
    return buffer.getvalue()


def run_all_datasets(sizes=BATCH_SIZES, repeats=3):
    """Benchmark all locally available Kaggle CSVs; preserve dataset identities."""
    if any(n not in BATCH_SIZES for n in sizes):
        raise ValueError("Kích thước benchmark không hợp lệ")
    all_rows = []
    missing = []
    for key, cfg in DATASETS.items():
        source = dataset_path(key)
        if not source.is_file():
            missing.append(key)
            continue
        dataset_rows = []
        try:
            for n in sizes:
                out = ROOT / 'results' / 'powerbi' / ('batch_' + key + '_' + str(n) + '.csv')
                rows = run_csv(source, cfg['column'], out, limit=n, repeats=repeats)
                for row in rows:
                    row['dataset'] = key
                dataset_rows.extend(rows)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            missing.append(key + ': ' + str(exc))
            continue
        all_rows.extend(dataset_rows)
    if not all_rows:
        raise ValueError('Không có CSV hợp lệ để chạy. ' + '; '.join(missing))
    BATCH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_OUTPUT.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    record_history(all_rows)
    return all_rows, missing


def clear_history_form():
    return ("<form action='/clear-history' method='post' "
            "onsubmit=\"return confirm('Xóa TOÀN BỘ lịch sử benchmark? Hành động này không thể hoàn tác.');\" "
            "style='margin:16px 0'>"
            "<input type='hidden' name='confirm' value='DELETE_HISTORY'>"
            "<button type='submit' style='background:#b42332;color:white;border:0;padding:11px 18px;border-radius:10px;cursor:pointer'>"
            "Xóa toàn bộ lịch sử</button></form>")


def record_history(rows):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    fresh = not HISTORY.exists() or HISTORY.stat().st_size == 0
    with HISTORY.open('a', newline='', encoding='utf-8-sig' if fresh else 'utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=HISTORY_FIELDS)
        if fresh:
            writer.writeheader()
        writer.writerows(rows)




def dataset_quality_report():
    """Inspect local Kaggle CSVs without loading them into memory."""
    report = []
    for key, cfg in DATASETS.items():
        path = dataset_path(key)
        info = {'dataset': key, 'title': cfg['title'], 'file': cfg['file'],
                'column': cfg['column'], 'exists': path.is_file(),
                'rows': 0, 'valid_numeric': 0, 'missing_numeric': 0,
                'invalid_numeric': 0, 'bytes': 0, 'error': ''}
        if path.is_file():
            info['bytes'] = path.stat().st_size
            try:
                ensure_csv_data(path)
                with path.open('r', encoding='utf-8-sig', newline='') as stream:
                    reader = csv.DictReader(stream)
                    if not reader.fieldnames or cfg['column'] not in reader.fieldnames:
                        info['error'] = 'Missing column: ' + cfg['column']
                    else:
                        import math
                        for row in reader:
                            info['rows'] += 1
                            value = (row.get(cfg['column']) or '').strip()
                            if not value:
                                info['missing_numeric'] += 1
                            else:
                                try:
                                    number = float(value.replace(',', ''))
                                    if math.isfinite(number): info['valid_numeric'] += 1
                                    else: info['invalid_numeric'] += 1
                                except ValueError:
                                    info['invalid_numeric'] += 1
            except (OSError, UnicodeError, csv.Error, ValueError) as exc:
                info['error'] = str(exc)
        report.append(info)
    return report


def quality_page():
    rows = dataset_quality_report()
    cells = ''.join('<tr>' + ''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in
        ('title','exists','rows','valid_numeric','missing_numeric','invalid_numeric','error'))+'</tr>' for r in rows)
    body = "<div class='panel'><h1>Dataset Quality Check</h1><p>Kiểm tra trực tiếp 3 CSV Kaggle trên máy, không tạo số liệu giả. Tệp lớn có thể mất thời gian đọc.</p><p><a class=download-btn href='/export-quality' role=button><span aria-hidden=true>↓</span> Tải báo cáo chất lượng CSV</a> <a href='/batch'>Benchmark All</a></p><div style='overflow:auto'><table><tr><th>Dataset</th><th>Exists</th><th>Rows</th><th>Valid</th><th>Missing</th><th>Invalid</th><th>Error</th></tr>"+cells+"</table></div></div>"
    return page_shell('Data Quality',body)

def comparison_page():
    """Offline cross-dataset comparison from measured batch CSV only."""
    if not BATCH_OUTPUT.is_file():
        return page_shell('Compare', "<div class='panel'><h1>Compare datasets</h1><p>Chưa có kết quả. Vào <a href='/batch'>Benchmark All</a> để chạy trên CSV Kaggle đã tải.</p></div>")
    with BATCH_OUTPUT.open(encoding='utf-8-sig', newline='') as stream:
        records = list(csv.DictReader(stream))
    valid=[]
    for row in records:
        if row.get('status') != 'ok': continue
        try:
            ms=float(row['median_ms']); n=int(row['n'])
            if ms < 0 or n <= 0: continue
            valid.append((row['dataset'],row['algorithm'],n,ms))
        except (ValueError,KeyError,TypeError): continue
    if not valid:
        return page_shell('Compare', "<div class='panel'><h1>Compare datasets</h1><p>Không có kết quả benchmark hợp lệ.</p></div>")
    datasets=sorted({r[0] for r in valid}); sizes=sorted({r[2] for r in valid}); algos=sorted({r[1] for r in valid})
    cards=f"<div class='panel'><h1>Cross-dataset comparison</h1><p>{len(datasets)} datasets · {len(algos)} algorithms · {len(sizes)} sample sizes. Chỉ dùng kết quả đo thực tế (status=ok).</p><p><a class=download-btn href='/export-batch' role=button><span aria-hidden=true>↓</span> Export Power BI CSV</a> <a href='/batch'>Benchmark All</a></p></div>"
    for dataset in datasets:
        cards += '<div class="panel"><h2>'+html.escape(DATASETS.get(dataset,{}).get('title',dataset))+'</h2>'
        for n in sizes:
            group=sorted([(a,t) for d,a,k,t in valid if d==dataset and k==n],key=lambda x:x[1])
            if not group: continue
            top=max(t for _,t in group) or 1
            cards+=f'<h3>n = {n:,}</h3>'
            for algo,ms in group:
                pct=max(0.5,ms/top*100)
                cards+='<div class="comparison-row"><span>'+html.escape(algo)+'</span><div style="background:#e8f0f2;border-radius:5px;overflow:hidden"><div style="height:17px;background:#087f82;width:'+format(pct,'.2f')+'%"></div></div><span>'+format(ms,'.4f')+' ms</span></div>'
        cards+='</div>'
    cards+="<div class='panel'><p>So sánh chỉ có ý nghĩa khi cùng máy, cùng n, số lần lặp và điều kiện chạy tương đương. Các thuật toán bị skip/error không được vẽ.</p></div>"
    return page_shell('Compare',cards)


def insights_page(query):
    """Interactive server-rendered filters over actual batch measurements."""
    if not BATCH_OUTPUT.exists():
        return page_shell('Insights', "<div class='panel'><h1>Benchmark Insights</h1><p>Chưa có dữ liệu thực nghiệm. Hãy chạy <a href='/batch'>Benchmark All</a> trước.</p></div>")
    with BATCH_OUTPUT.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    datasets = sorted({r.get('dataset','') for r in rows if r.get('dataset')})
    algorithms = sorted({r.get('algorithm','') for r in rows if r.get('algorithm')})
    sizes = sorted({r.get('n','') for r in rows if r.get('n')}, key=lambda x: int(x) if x.isdigit() else 0)
    chosen = {k:query.get(k,['all'])[0] for k in ('dataset','algorithm','n')}
    def selector(key, options, title):
        result = '<label>'+title+' <select name="'+key+'"><option value="all">Tất cả</option>'
        for value in options:
            selected = ' selected' if chosen[key] == value else ''
            result += '<option value="'+html.escape(value,quote=True)+'"'+selected+'>'+html.escape(value)+'</option>'
        return result+'</select></label>'
    filtered = [r for r in rows if r.get('status') == 'ok' and all(chosen[k]=='all' or r.get(k)==chosen[k] for k in chosen)]
    valid = []
    for r in filtered:
        try:
            ms = float(r['median_ms'])
            if 0 <= ms < float('inf'): valid.append((r,ms))
        except (ValueError, TypeError, KeyError): pass
    valid.sort(key=lambda item: item[1])
    form = '<form method="get" action="/insights">'+selector('dataset',datasets,'Dataset')+selector('algorithm',algorithms,'Thuật toán')+selector('n',sizes,'Kích thước')+'<button type="submit">Áp dụng bộ lọc</button></form>'
    body = '<div class="panel"><h1>Benchmark Insights</h1><p>Lọc trực tiếp các kết quả đo thực tế (status=ok). Không tạo dữ liệu giả.</p>'+form+'<p><a class=download-btn href="/export-batch" role=button><span aria-hidden=true>↓</span> Tải toàn bộ dữ liệu Power BI</a> <a href="/batch">Chạy benchmark mới</a></p></div>'
    if valid:
        maximum = max(t for _,t in valid) or 1
        body += '<div class="panel"><h2>Kết quả ('+str(len(valid))+' dòng)</h2><p>Thấp nhất: '+format(valid[0][1],'.4f')+' ms · Cao nhất: '+format(valid[-1][1],'.4f')+' ms</p>'
        for row,ms in valid[:100]:
            label = ' / '.join((row.get('dataset',''),row.get('algorithm',''),'n='+row.get('n','')))
            body += '<div style="margin:12px 0"><div>'+html.escape(label)+' — '+format(ms,'.4f')+' ms</div><div style="background:#e7eff2;border-radius:4px"><div style="background:#087f82;height:13px;width:'+format(max(0.4,ms/maximum*100),'.2f')+'%"></div></div></div>'
        if len(valid)>100: body += '<p>Chỉ hiển thị 100 dòng nhanh nhất. Tải CSV để xem đầy đủ.</p>'
        body += '</div>'
    else: body += '<div class="panel">Không có kết quả hợp lệ phù hợp với bộ lọc.</div>'
    return page_shell('Insights',body)


def executive_report_page(query):
    """Executive summary calculated exclusively from real measured benchmark rows."""
    if not BATCH_OUTPUT.exists():
        return page_shell('Executive Report', "<div class='panel'><h1>Executive Report</h1><p>Chưa có dữ liệu đo. <a href='/batch'>Chạy Benchmark All</a> trước.</p></div>")
    with BATCH_OUTPUT.open(encoding='utf-8-sig', newline='') as f:
        raw = list(csv.DictReader(f))
    valid = []
    for r in raw:
        if r.get('status') != 'ok':
            continue
        try:
            ms = float(r['median_ms']); size = int(r['n'])
            peak = float(r['peak_kb']) if r.get('peak_kb') not in ('', None) else None
            if not (0 <= ms < float('inf') and size > 0):
                continue
            if peak is not None and not (0 <= peak < float('inf')):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        valid.append((r,ms,size,peak))
    if not valid:
        return page_shell('Executive Report', "<div class='panel'><h1>Executive Report</h1><p>Không có kết quả đo hợp lệ.</p></div>")
    dataset = query.get('dataset',['all'])[0]
    options = sorted({r['dataset'] for r,_,_,_ in valid})
    if dataset not in options and dataset != 'all': dataset = 'all'
    selected = [v for v in valid if dataset == 'all' or v[0]['dataset'] == dataset]
    groups = {}
    for r,ms,n,peak in selected:
        groups.setdefault((r['dataset'],n),[]).append((r,ms,peak))
    lines = []
    for (ds,n),measurements in sorted(groups.items()):
        winner = min(measurements,key=lambda x:x[1])
        lines.append((ds,n,winner[0]['algorithm'],winner[1],winner[2],len({r['algorithm'] for r,_,_ in measurements})))
    opts = '<option value="all">Tất cả</option>' + ''.join('<option value="'+html.escape(v,quote=True)+'"'+(' selected' if v==dataset else '')+'>'+html.escape(v)+'</option>' for v in options)
    table = ''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (ds,n,algo,format(ms,'.4f'),format(kb,'.1f') if kb is not None else '—',count))+'</tr>' for ds,n,algo,ms,kb,count in lines)
    body = '<div class="panel"><h1>Executive Benchmark Report</h1><p>Tổng hợp từ số liệu thực đo; thuật toán nhanh nhất được chọn trong từng dataset và kích thước mẫu. Không dùng dữ liệu mô phỏng để thay thế kết quả Kaggle.</p><form action="/executive" method="get"><label>Dataset <select name="dataset">'+opts+'</select></label><button>Xem báo cáo</button></form><p><strong>'+str(len(selected))+'</strong> kết quả hợp lệ · <strong>'+str(len(lines))+'</strong> nhóm so sánh · <strong>'+str(len({r["dataset"] for r,_,_,_ in selected}))+'</strong> dataset</p><p><a class=download-btn href="/export-executive" role=button><span aria-hidden=true>↓</span> Xuất báo cáo CSV</a> <a href="/insights">Insights</a> <a href="/batch">Benchmark All</a></p></div>'
    body = body.replace('href="/export-executive"', 'href="/export-executive?' + html.escape(urlencode({'dataset': dataset}), quote=True) + '"')
    body += '<div class="panel"><h2>Thuật toán nhanh nhất theo nhóm</h2><div style="overflow:auto"><table><tr><th>Dataset</th><th>n</th><th>Algorithm</th><th>Median ms</th><th>Peak KB</th><th>Algorithms measured</th></tr>'+table+'</table></div></div>'
    body += '<div class="panel"><p><strong>Lưu ý:</strong> Không so sánh trực tiếp kết quả khác kích thước mẫu hoặc khác cấu hình máy. Số đo peak KB là giá trị do công cụ benchmark thu thập, không phải tổng RAM hệ thống.</p></div>'
    return page_shell('Executive Report',body)


def executive_csv(dataset='all'):
    if not BATCH_OUTPUT.exists(): raise ValueError('Chưa có benchmark tổng hợp')
    with BATCH_OUTPUT.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    groups={}
    for r in rows:
        if dataset != 'all' and r.get('dataset') != dataset: continue
        if r.get('status') != 'ok': continue
        try:
            ms=float(r['median_ms']); n=int(r['n'])
            if not (0 <= ms < float('inf') and n > 0): continue
        except (ValueError,TypeError,KeyError): continue
        key=(r.get('dataset',''),n)
        if key not in groups or ms < float(groups[key]['median_ms']): groups[key]=r
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=['dataset','n','algorithm','median_ms','peak_kb','run_id','run_utc'])
    writer.writeheader()
    for (ds,n),r in sorted(groups.items()):
        writer.writerow({k:(n if k=='n' else ds if k=='dataset' else r.get(k,'')) for k in writer.fieldnames})
    return stream.getvalue().encode('utf-8-sig')


def selection_form(path, title, source=''):
    cols = numeric_columns(path)
    if not cols:
        raise ValueError('Không tìm thấy cột số trong CSV')
    return page_shell('Chọn cột', selection_body(path.name, cols, source, title)).encode()


def resolve_source(reference):
    """Resolve an explicit form source, keeping uploads in separate directories."""
    if reference.startswith('local:'):
        path = dataset_path(reference.removeprefix('local:'))
    else:
        # The fallback keeps old forms compatible with pre-refresh uploads.
        path = (UPLOAD / (reference or 'uploaded_dataset.csv')).resolve()
        if not path.is_relative_to(UPLOAD.resolve()):
            raise ValueError('Nguồn CSV không hợp lệ')
    if not path.is_file() or path.suffix.lower() != '.csv':
        raise ValueError('Không tìm thấy CSV. Vui lòng chọn lại dữ liệu.')
    return path


def experiment_overview():
    with SUMMARY.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    measured = [row for row in rows if row.get('status') == 'ok']
    raw = SUMMARY.with_name('raw.csv')
    observations = 0
    if raw.is_file():
        with raw.open(encoding='utf-8-sig', newline='') as stream:
            observations = sum(row.get('status') == 'ok' for row in csv.DictReader(stream))
    return {
        'configurations': len(rows), 'measured': len(measured),
        'skipped': sum(row.get('status') == 'skipped' for row in rows),
        'observations': observations,
        'high_cv': sum(float(row.get('cv_pct') or 0) > 10 for row in measured),
        'seed': rows[0].get('seed', '—') if rows else '—',
        'repeats': measured[0].get('repeats', '—') if measured else '—',
        'figures': sorted(path.name for path in FIGURES.glob('*.svg')),
    }


def readiness_report():
    """Actionable preflight checks; never claims that Kaggle or Power BI was executed."""
    checks = []
    for key, cfg in DATASETS.items():
        path = dataset_path(key)
        status, detail = dataset_state(key)
        checks.append({'check': cfg['title'], 'status': status,
                       'detail': detail,
                       'bytes': path.stat().st_size if path.is_file() else 0})
    for label, path in [('Batch CSV', BATCH_OUTPUT), ('History CSV', HISTORY), ('Latest benchmark CSV', OUTPUT)]:
        checks.append({'check': label, 'status': 'READY' if path.is_file() else 'MISSING',
                       'detail': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size if path.is_file() else 0})
    return checks


def readiness_page():
    checks = readiness_report()
    cells = ''.join('<tr><td>'+html.escape(x['check'])+'</td><td>'+html.escape(x['status'])+
                    '</td><td>'+html.escape(x['detail'])+'</td><td>'+str(x['bytes'])+'</td></tr>' for x in checks)
    body = ("<div class='panel'><h1>Project Readiness / Kiểm tra trước nghiệm thu</h1>"
            "<p>Trạng thái file tại máy hiện tại, không phải kết quả kiểm thử giao diện Windows hoặc Power BI Desktop.</p>"
            "<table><tr><th>Hạng mục</th><th>Trạng thái</th><th>Đường dẫn / hướng dẫn</th><th>Bytes</th></tr>"+cells+"</table>"
            "<p><a class=download-btn href='/export-readiness' role=button><span aria-hidden=true>↓</span> Xuất báo cáo CSV</a> <a href='/batch'>Chạy Benchmark All</a></p></div>")
    return page_shell('Project Readiness', body)


def powerbi_health_report():
    """Validate export files and benchmark history for Power BI import."""
    checks = []
    for label, path, required in [
        ('Batch benchmark', BATCH_OUTPUT, ('dataset','algorithm','n','median_ms','status')),
        ('Experiment history', HISTORY, ('dataset','algorithm','n','median_ms','status')),
        ('Latest benchmark', OUTPUT, ('algorithm','median_ms','status')),
    ]:
        item = {'artifact':label,'status':'MISSING','rows':0,'details':str(path.relative_to(ROOT))}
        if path.is_file():
            try:
                with path.open(encoding='utf-8-sig',newline='') as stream:
                    reader=csv.DictReader(stream)
                    missing=[field for field in required if field not in (reader.fieldnames or [])]
                    if missing:
                        item['status']='INVALID'
                        item['details']='Missing columns: '+', '.join(missing)
                    else:
                        item['rows']=sum(1 for _ in reader)
                        item['status']='READY' if item['rows'] else 'EMPTY'
            except (OSError, UnicodeError, csv.Error) as exc:
                item['status']='ERROR'
                item['details']=str(exc)
        checks.append(item)
    return checks


def powerbi_health_page():
    rows=''.join('<tr><td>'+html.escape(str(x['artifact']))+'</td><td>'+html.escape(x['status'])+'</td><td>'+str(x['rows'])+'</td><td>'+html.escape(x['details'])+'</td></tr>' for x in powerbi_health_report())
    body=("<div class='panel'><h1>Power BI Export Health</h1>"
          "<p>Kiểm tra CSV có đủ cột và có dữ liệu thực nghiệm trước khi nhập Power BI. Không tạo kết quả giả.</p>"
          "<table><tr><th>File</th><th>Status</th><th>Rows</th><th>Details</th></tr>"+rows+"</table>"
          "<p><a class=download-btn href='/export-powerbi-health' role=button><span aria-hidden=true>↓</span> Export validation CSV</a> <a href='/batch'>Benchmark All</a></p></div>")
    return page_shell('Power BI Export Health',body)



def experiment_validation_report():
    """Audit recorded benchmark rows for schema, numeric validity and comparability."""
    issues = []
    stats = {'rows': 0, 'valid': 0, 'invalid': 0, 'groups': 0}
    if not HISTORY.is_file():
        return stats, [{'row': '', 'severity': 'INFO', 'issue': 'history.csv chưa tồn tại', 'dataset': '', 'algorithm': ''}]
    groups = {}
    try:
        with HISTORY.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            required = ('dataset', 'algorithm', 'n', 'median_ms', 'status')
            absent = [x for x in required if x not in (reader.fieldnames or [])]
            if absent:
                return stats, [{'row': '', 'severity': 'ERROR', 'issue': 'Thiếu cột: ' + ', '.join(absent), 'dataset': '', 'algorithm': ''}]
            for line, record in enumerate(reader, 2):
                stats['rows'] += 1
                error = ''
                try:
                    n = int(record['n'])
                    duration = float(record['median_ms'])
                    if n <= 0 or not (0 <= duration < float('inf')): error = 'n hoặc median_ms không hợp lệ'
                except (TypeError, ValueError, OverflowError):
                    error = 'Không thể đọc n hoặc median_ms'
                if not record.get('dataset') or not record.get('algorithm'):
                    error = 'Thiếu dataset hoặc algorithm'
                if record.get('status', '').lower() not in ('ok', 'success', 'passed'):
                    error = error or 'Kết quả không thành công: ' + record.get('status', '')
                if error:
                    stats['invalid'] += 1
                    issues.append({'row': line, 'severity': 'WARNING', 'issue': error, 'dataset': record.get('dataset',''), 'algorithm': record.get('algorithm','')})
                else:
                    stats['valid'] += 1
                    groups.setdefault((record['dataset'], n), set()).add(record['algorithm'])
        stats['groups'] = len(groups)
        for (dataset, n), algorithms in groups.items():
            if len(algorithms) < 2:
                issues.append({'row': '', 'severity': 'INFO', 'issue': f'Chỉ có {len(algorithms)} thuật toán tại n={n}; chưa đủ để so sánh', 'dataset': dataset, 'algorithm': ', '.join(sorted(algorithms))})
    except (OSError, UnicodeError, csv.Error) as exc:
        issues.append({'row': '', 'severity': 'ERROR', 'issue': str(exc), 'dataset': '', 'algorithm': ''})
    return stats, issues


def experiment_validation_page():
    stats, issues = experiment_validation_report()
    summary = ' · '.join(f'{key}: {value}' for key, value in stats.items())
    rows = ''.join('<tr>' + ''.join('<td>' + html.escape(str(item[key])) + '</td>' for key in ('row','severity','issue','dataset','algorithm')) + '</tr>' for item in issues[:200])
    body = ('<div class="panel"><h1>Experiment Validation</h1><p>Kiểm tra tính hợp lệ của lịch sử benchmark và khả năng so sánh kết quả. Không tạo dữ liệu giả.</p>'
            '<p><strong>' + html.escape(summary) + '</strong></p>'
            '<p><a class=download-btn href="/export-validation" role=button><span aria-hidden=true>↓</span> Tải báo cáo CSV</a> <a href="/history">Lịch sử</a> <a href="/batch">Benchmark All</a></p>'
            '<table><tr><th>Row</th><th>Severity</th><th>Issue</th><th>Dataset</th><th>Algorithm</th></tr>' + rows + '</table></div>')
    return page_shell('Experiment Validation', body)


def page_shell(title, body):
    return render_page(title, body)


def experiment_audit():
    """Summarize recorded experiments without fabricating measurements."""
    from collections import Counter
    stats = {'total': 0, 'valid': 0, 'failed': 0, 'datasets': Counter(),
             'algorithms': Counter(), 'sizes': Counter(), 'runs': set(), 'issues': []}
    if not HISTORY.exists():
        stats['issues'].append('No benchmark history yet')
        return stats
    try:
        with HISTORY.open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                stats['total'] += 1
                if row.get('status', '').strip().lower() == 'ok':
                    stats['valid'] += 1
                else:
                    stats['failed'] += 1
                stats['datasets'][row.get('dataset') or 'unknown'] += 1
                stats['algorithms'][row.get('algorithm') or 'unknown'] += 1
                stats['sizes'][row.get('n') or 'unknown'] += 1
                if row.get('run_id'): stats['runs'].add(row['run_id'])
    except (OSError, csv.Error, UnicodeError) as exc:
        stats['issues'].append(str(exc))
    return stats


def audit_page():
    stats = experiment_audit()
    def table(counter, label):
        rows = ''.join('<tr><td>'+html.escape(str(k))+'</td><td>'+str(v)+'</td></tr>'
                       for k, v in sorted(counter.items()))
        return '<h2>'+label+'</h2><table><tr><th>Name</th><th>Rows</th></tr>'+rows+'</table>'
    body = ("<div class='panel'><h1>Experiment Audit / Kiểm tra thực nghiệm</h1>"
            "<p>Thống kê dựa trên history.csv, không phải dữ liệu Kaggle giả lập.</p>"
            f"<p>Total: {stats['total']} · Valid: {stats['valid']} · Failed/skipped: {stats['failed']} · Unique runs: {len(stats['runs'])}</p>"
            "<p><a class=download-btn href='/export-history' role=button><span aria-hidden=true>↓</span> Download raw history CSV</a> <a href='/batch'>Run Benchmark All</a></p></div>")
    for name in stats['issues']:
        body += '<div class="panel">'+html.escape(name)+'</div>'
    body += '<div class="panel">'+table(stats['datasets'],'Datasets')+table(stats['algorithms'],'Algorithms')+table(stats['sizes'],'Sample sizes')+'</div>'
    return page_shell('Experiment Audit',body)


def reproducibility_manifest():
    """Provide a truthful, read-only inventory of source data and experiment outputs."""
    datasets = []
    for key, cfg in DATASETS.items():
        source = dataset_path(key)
        status, detail = dataset_state(key)
        item = {"dataset": key, "kaggle_slug": cfg["slug"], "column": cfg["column"],
                "present": status == 'READY', "status": status, "detail": detail,
                "relative_path": str(source.relative_to(ROOT)).replace("\\", "/")}
        if source.is_file():
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            item.update(size_bytes=source.stat().st_size, sha256=digest.hexdigest())
        datasets.append(item)
    return {"generated_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "platform": platform.platform(),
            "batch_sizes": list(BATCH_SIZES), "dataset_inventory": datasets,
            "history_present": HISTORY.is_file(), "batch_output_present": BATCH_OUTPUT.is_file(),
            "audit": {k: (dict(v) if hasattr(v, 'items') else len(v) if isinstance(v, set) else v)
                      for k, v in experiment_audit().items()}}


def reproducibility_page():
    manifest = reproducibility_manifest()
    rows = ''.join('<tr><td>'+html.escape(d['dataset'])+'</td><td>'+('Available' if d['present'] else 'Missing')+
                   '</td><td>'+html.escape(d.get('sha256', '—'))+'</td></tr>'
                   for d in manifest['dataset_inventory'])
    body = ("<div class='panel'><h1>Reproducibility / Tái lập thí nghiệm</h1>"
            "<p>Kiểm tra phiên bản Python, nguồn CSV, SHA-256 và số liệu audit. "
            "Không tạo benchmark giả khi dữ liệu chưa có.</p>"
            "<p><a class=download-btn href='/export-manifest' role=button><span aria-hidden=true>↓</span> Download experiment_manifest.json</a></p>"
            "<table><tr><th>Dataset</th><th>CSV</th><th>SHA-256</th></tr>"+rows+"</table>"
            "<p>Python: "+html.escape(manifest['python'])+" · Total history rows: "+
            str(manifest['audit']['total'])+"</p></div>")
    return page_shell('Reproducibility', body)


def build_submission_bundle():
    """Export existing evidence only; never synthesize missing benchmark results."""
    stream = io.BytesIO()
    available = {
        'powerbi/all_datasets_benchmark.csv': BATCH_OUTPUT,
        'powerbi/history.csv': HISTORY,
        'powerbi/final_benchmark.csv': OUTPUT,
        'powerbi/FINAL_DASHBOARD.html': OUTPUT.with_name('FINAL_DASHBOARD.html'),
        'powerbi/DAX_Measures.txt': ROOT / 'powerbi' / 'DAX_Measures.txt',
        'powerbi/PowerQuery_SortingBenchmark.m': ROOT / 'powerbi' / 'PowerQuery_SortingBenchmark.m',
    }
    included = [name for name, path in available.items() if path.is_file()]
    missing = [name for name, path in available.items() if not path.is_file()]
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in included:
            archive.write(available[name], arcname=name)
        archive.writestr('experiment_manifest.json', json.dumps(reproducibility_manifest(), ensure_ascii=False, indent=2))
        archive.writestr('README_SUBMISSION.txt',
            'SortingLab V18 - Evidence Bundle\nIncluded:\n' + '\n'.join(included) +
            '\n\nMissing (not generated):\n' + '\n'.join(missing) +
            '\n\nPower BI Desktop: Get Data > Text/CSV; select all_datasets_benchmark.csv or history.csv.\n'
            'This bundle does not contain a native .pbix file.\n')
    return stream.getvalue()


def submission_page():
    available = [('Batch benchmark', BATCH_OUTPUT), ('History', HISTORY),
                 ('Latest benchmark', OUTPUT), ('Power BI DAX', ROOT / 'powerbi' / 'DAX_Measures.txt')]
    rows = ''.join('<tr><td>' + html.escape(label) + '</td><td>' +
                   ('READY' if path.is_file() else 'MISSING') + '</td></tr>'
                   for label, path in available)
    body = "<div class='panel'><h1>Submission Center</h1><p>Đóng gói bằng chứng thực nghiệm, CSV Power BI, DAX và manifest thành một file ZIP. File chưa có sẽ được ghi rõ là MISSING; không tự tạo kết quả giả.</p><p><a class=download-btn href='/export-submission' role=button><span aria-hidden=true>↓</span> Tải Evidence Bundle (.zip)</a> <a href='/batch'>Benchmark All</a></p><table><tr><th>Artifact</th><th>Status</th></tr>" + rows + '</table></div>'
    return page_shell('Submission Center', body)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json(self, status, payload):
        self.respond(status, json.dumps(payload, ensure_ascii=False).encode())

    def do_GET(self):
        path = urlsplit(self.path)
        query = parse_qs(path.query)
        try:
            if path.path == "/":
                body = (ROOT / 'dashboard' / 'experiment.html').read_text(encoding='utf-8')
                self.respond(200, page_shell('Experiment Data', body).encode(), 'text/html; charset=utf-8')
            elif path.path.startswith('/assets/'):
                name = path.path.removeprefix('/assets/')
                assets = ROOT / 'dashboard' / 'assets'
                if name not in {item.name for item in assets.iterdir() if item.is_file()}:
                    self.json(404, {'error': 'Không tìm thấy tài nguyên.'})
                    return
                self.respond(200, (assets / name).read_bytes(), mimetypes.guess_type(name)[0] or 'application/octet-stream')
            elif path.path == '/tools':
                self.respond(200, page_shell('Công cụ nâng cao', tools_body()).encode(), 'text/html; charset=utf-8')
            elif path.path == "/real-data":
                datasets = dataset_choices()
                self.respond(200, page_shell('CSV', real_data_body(datasets)).encode(), 'text/html; charset=utf-8')
            elif path.path == '/powerbi-guide':
                body = "<div class='panel'><h1>Power BI Desktop</h1><p>Nhập tệp Excel Benchmark vào Power BI Desktop bằng Get Data → Excel workbook. Chọn bảng Benchmark.</p><p><a class=download-btn href='/export-batch-excel' role=button><span aria-hidden=true>↓</span> Tải Excel Benchmark All</a> <a class=download-btn href='/export-excel' role=button><span aria-hidden=true>↓</span> Tải Excel lần chạy mới nhất</a> <a class=download-btn href='/export' role=button><span aria-hidden=true>↓</span> Tải CSV</a> <a class=download-btn href='/export-m' role=button><span aria-hidden=true>↓</span> Tải Power Query M</a> <a class=download-btn href='/export-dax' role=button><span aria-hidden=true>↓</span> Tải DAX</a></p></div>"
                self.respond(200,page_shell('Power BI',body).encode(),'text/html; charset=utf-8')
            elif path.path == '/export-m':
                self.respond(200,(ROOT/'powerbi'/'PowerQuery_SortingBenchmark.m').read_bytes(),'text/plain; charset=utf-8')
            elif path.path == '/export-dax':
                self.respond(200,(ROOT/'powerbi'/'DAX_Measures.txt').read_bytes(),'text/plain; charset=utf-8')
            elif path.path in ('/results', '/powerbi'):
                view = query.get('view', ['latest' if path.path == '/powerbi' else 'overview'])[0]
                if view == 'overview':
                    result = executive_report_page(query)
                elif view == 'compare':
                    result = comparison_page()
                elif view == 'explore':
                    result = insights_page(query)
                elif view == 'latest':
                    result = page_shell('Dashboard', latest_body(OUTPUT.is_file()))
                else:
                    raise ValueError('Chế độ xem không hợp lệ')
                self.respond(200, result.encode(), 'text/html; charset=utf-8')
            elif path.path == '/quality':
                self.respond(200,quality_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/export-quality':
                records = dataset_quality_report()
                stream = io.StringIO()
                writer = csv.DictWriter(stream, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
                self.respond(200,stream.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
            elif path.path == '/reproducibility':
                self.respond(200,reproducibility_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/export-manifest':
                payload = json.dumps(reproducibility_manifest(), ensure_ascii=False, indent=2).encode('utf-8')
                self.respond(200,payload,'application/json; charset=utf-8')
            elif path.path == '/validation':
                self.respond(200, experiment_validation_page().encode(), 'text/html; charset=utf-8')
            elif path.path == '/export-validation':
                _, records = experiment_validation_report()
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=['row','severity','issue','dataset','algorithm'])
                writer.writeheader()
                writer.writerows(records)
                self.respond(200, output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')
            elif path.path == '/powerbi-health':
                self.respond(200,powerbi_health_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/export-powerbi-health':
                output=io.StringIO()
                writer=csv.DictWriter(output,fieldnames=['artifact','status','rows','details'])
                writer.writeheader()
                writer.writerows(powerbi_health_report())
                self.respond(200,output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
            elif path.path == '/submission':
                self.respond(200, submission_page().encode(), 'text/html; charset=utf-8')
            elif path.path == '/export-submission':
                self.respond(200, build_submission_bundle(), 'application/zip')
            elif path.path == '/readiness':
                self.respond(200,readiness_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/export-readiness':
                output = io.StringIO()
                writer = csv.DictWriter(output,fieldnames=['check','status','detail','bytes'])
                writer.writeheader()
                writer.writerows(readiness_report())
                self.respond(200,output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
            elif path.path == '/audit':
                self.respond(200,audit_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/executive':
                self.respond(200,executive_report_page(query).encode(),'text/html; charset=utf-8')
            elif path.path == '/export-executive':
                self.respond(200,executive_csv(query.get('dataset', ['all'])[0]),'text/csv; charset=utf-8')
            elif path.path == '/insights':
                self.respond(200,insights_page(query).encode(),'text/html; charset=utf-8')
            elif path.path == '/compare':
                self.respond(200,comparison_page().encode(),'text/html; charset=utf-8')
            elif path.path == '/batch':
                datasets = dataset_choices()
                self.respond(200, page_shell('Benchmark All', batch_body(datasets)).encode(), 'text/html; charset=utf-8')
            elif path.path == '/export-batch-excel':
                data = benchmark_excel_bytes(BATCH_OUTPUT)
                self.respond(200, data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='SortingLab_Benchmark_All.xlsx')
            elif path.path == '/export-excel':
                data = benchmark_excel_bytes(OUTPUT)
                self.respond(200, data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='SortingLab_Latest_Benchmark.xlsx')
            elif path.path == '/export-batch':
                if not BATCH_OUTPUT.exists(): raise ValueError('Chưa có benchmark tổng hợp')
                self.respond(200,BATCH_OUTPUT.read_bytes(),'text/csv; charset=utf-8')
            elif path.path == '/history':
                if HISTORY.exists():
                    with HISTORY.open(newline='',encoding='utf-8-sig') as f:
                        records=list(csv.DictReader(f))[-120:]
                    cells=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in ('run_utc','dataset','column','algorithm','n','median_ms','status'))+'</tr>' for r in reversed(records))
                    body="<div class='panel'><h1>Lịch sử benchmark</h1><p><a class=download-btn href='/export-history' role=button><span aria-hidden=true>↓</span> Tải toàn bộ lịch sử CSV cho Power BI</a></p>"+clear_history_form()+"<div style='overflow:auto'><table><tr><th>UTC</th><th>Dataset</th><th>Cột</th><th>Thuật toán</th><th>n</th><th>Median ms</th><th>Trạng thái</th></tr>"+cells+"</table></div></div>"
                else:
                    body="<div class='panel'><h1>Lịch sử benchmark</h1><p>Chưa có lần chạy nào.</p></div>"
                self.respond(200,page_shell('Lịch sử',body).encode(),'text/html; charset=utf-8')
            elif path.path == '/export-history':
                if not HISTORY.exists(): raise ValueError('Chưa có lịch sử benchmark')
                self.respond(200,HISTORY.read_bytes(),'text/csv; charset=utf-8')
            elif path.path == '/export':
                if not OUTPUT.exists(): raise ValueError('Chưa có dữ liệu benchmark')
                self.respond(200,OUTPUT.read_bytes(),'text/csv; charset=utf-8')
            elif path.path == '/report':
                report=OUTPUT.with_name('FINAL_DASHBOARD.html')
                if not report.exists(): raise ValueError('Chưa có dashboard')
                self.respond(200,report.read_bytes(),'text/html; charset=utf-8')
            elif path.path == "/api/overview":
                self.json(200, experiment_overview())
            elif path.path == "/api/summary":
                with SUMMARY.open(encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
                self.json(200, [r for r in rows if r["experiment"] == "E1E2"])
            elif path.path == "/api/demo":
                n = int(query.get("n", ["1000"])[0])
                seed = int(query.get("seed", ["42"])[0])
                dist = query.get("distribution", ["random"])[0]
                if (n not in (100, 500, 1000, 2000)
                        or dist not in DISTRIBUTIONS or abs(seed) > 1000000):
                    raise ValueError(
                        "Chọn n=100, 500, 1000 hoặc 2000; "
                        "phân phối và seed hợp lệ."
                    )
                rows = []
                with benchmark_session():
                    for name in ALGORITHMS:
                        rows.extend(isolated((name, dist, n, seed, 5, "demo_web", True)))
                results = sorted(summarize(rows), key=lambda r: float(r.get("median_ms") or "inf"))
                data = generate(n, dist, seed)
                output = ALGORITHMS["timsort"](data)
                self.json(200, {
                    "rows": results, "first": output[:12], "last": output[-12:],
                    "n": n, "distribution": dist, "seed": seed,
                })
            elif path.path.startswith("/figures/"):
                name = path.path.removeprefix("/figures/")
                if name not in {p.name for p in FIGURES.glob("*.svg")}:
                    self.json(404, {"error": "Không có biểu đồ."})
                    return
                data = (FIGURES / name).read_bytes()
                self.respond(200, data, mimetypes.guess_type(name)[0] or "image/svg+xml")
            else:
                self.json(404, {"error": "Không tìm thấy."})
        except (ValueError, IndexError) as exc:
            self.json(400, {"error": str(exc)})
        except Exception as exc:
            self.json(500, {"error": f"Không thể tải dữ liệu: {exc}"})


    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>MAX_UPLOAD or (length==0 and self.path not in ('/use-local-kaggle','/kaggle-download','/batch-run','/clear-history')): raise ValueError('CSV phải nhỏ hơn 12 MB')
            if self.path == '/batch-run':
                self.rfile.read(length)
                with benchmark_session():
                    rows, missing = run_all_datasets()
                msg = 'Đã tạo '+str(len(rows))+' kết quả từ CSV cục bộ. Dataset thiếu hoặc không hợp lệ đã bỏ qua: '+('; '.join(missing) if missing else 'không có')
                body = "<div class='panel'><h1>Benchmark tổng hợp hoàn tất</h1><p>"+html.escape(msg)+"</p><p><a class=download-btn href='/export-batch-excel' role=button><span aria-hidden=true>↓</span> Tải Excel tổng hợp</a> <a class=download-btn href='/export-batch' role=button><span aria-hidden=true>↓</span> Tải CSV tổng hợp</a> <a href='/history'>Xem lịch sử</a> <a href='/batch'>Chạy lại</a></p></div>"
                self.respond(200,page_shell('Hoàn tất',body).encode(),'text/html; charset=utf-8')
            elif self.path == '/clear-history':
                params = parse_qs(self.rfile.read(length).decode('utf-8'))
                if params.get('confirm', [''])[0] != 'DELETE_HISTORY':
                    raise ValueError('Cần xác nhận trước khi xóa lịch sử')
                if HISTORY.exists():
                    HISTORY.unlink()
                body = "<div class='panel'><h1>Đã xóa lịch sử benchmark</h1><p>Các bản ghi trong history.csv đã được xóa. Dữ liệu Kaggle và kết quả benchmark mới nhất vẫn được giữ nguyên.</p><p><a href='/history'>Xem lịch sử</a> <a href='/batch'>Benchmark All</a></p></div>"
                self.respond(200, page_shell('Đã xóa lịch sử', body).encode(), 'text/html; charset=utf-8')
            elif self.path == '/use-local-kaggle':
                params=parse_qs(self.rfile.read(length).decode('utf-8'))
                key=params.get('dataset',['superstore'])[0]
                csv_path=dataset_path(key)
                if not csv_path.is_file(): raise ValueError('Chưa có file '+str(csv_path.relative_to(ROOT)))
                self.respond(200, selection_form(csv_path, 'Dữ liệu có sẵn', 'local:' + key), 'text/html; charset=utf-8')
            elif self.path == '/upload':
                content_type = self.headers.get('Content-Type', '')
                if not content_type.lower().startswith('multipart/form-data'):
                    raise ValueError('Yêu cầu tải lên phải là multipart/form-data')
                payload = self.rfile.read(length)
                message = BytesParser(policy=default).parsebytes(
                    b'MIME-Version: 1.0\r\nContent-Type: ' + content_type.encode('ascii')
                    + b'\r\n\r\n' + payload
                )
                if not message.is_multipart():
                    raise ValueError('Biểu mẫu tải lên không hợp lệ')
                parts = [part for part in message.iter_parts()
                         if part.get_param('name', header='content-disposition') == 'dataset']
                if len(parts) != 1:
                    raise ValueError('Vui lòng chọn đúng một file CSV')
                item = parts[0]
                filename = item.get_filename() or ''
                if not filename.lower().endswith('.csv'):
                    raise ValueError('Chỉ chấp nhận file CSV')
                raw = item.get_payload(decode=True)
                if raw is None:
                    raise ValueError('Không thể đọc nội dung CSV')
                if len(raw) > MAX_UPLOAD:
                    raise ValueError('File quá lớn')
                original_name = Path(filename.replace('\\', '/')).name
                if not original_name or len(original_name) > 180:
                    raise ValueError('Tên file CSV không hợp lệ hoặc quá dài')
                folder = UPLOAD / uuid.uuid4().hex
                folder.mkdir(parents=True)
                target = folder / original_name
                try:
                    target.write_bytes(raw)
                    result = selection_form(target, 'CSV của bạn', str(target.relative_to(UPLOAD)).replace('\\', '/'))
                except Exception:
                    shutil.rmtree(folder)
                    raise
                self.respond(200, result, 'text/html; charset=utf-8')
            elif self.path == '/kaggle-download':
                # Legacy button/link compatibility: prefer packaged local CSV.
                # Local CSVs provided by the user; Kaggle CLI is not required.
                params = parse_qs(self.rfile.read(length).decode('utf-8'))
                key = params.get('dataset', ['superstore'])[0]
                csv_path = dataset_path(key)
                if not csv_path.is_file():
                    raise ValueError('Không tìm thấy CSV cục bộ. Vui lòng đặt file vào data/kaggle/'+key+'/ hoặc tải CSV lên ở trang Real-life Data.')
                self.respond(200, selection_form(csv_path, 'Dữ liệu cục bộ: ' + DATASETS[key]['title'], 'local:' + key), 'text/html; charset=utf-8')
            elif self.path == '/benchmark':
                body=self.rfile.read(length).decode('utf-8')
                params=parse_qs(body)
                column=params.get('column',[''])[0]; limit=int(params.get('limit',['1000'])[0])
                target=resolve_source(params.get('source', [''])[0])
                if not target.exists() or column not in numeric_columns(target) or limit not in (100,500,1000,2000,4000,10000,50000):raise ValueError('Tham số không hợp lệ')
                with benchmark_session():
                    rows=run_csv(target,column,OUTPUT,limit=limit,repeats=3)
                    record_history(rows)
                    build(OUTPUT,OUTPUT.with_name('FINAL_DASHBOARD.html'))
                self.send_response(303);self.send_header('Location','/powerbi');self.send_header('Content-Length','0');self.end_headers()
            else:self.json(404,{'error':'Not found'})
        except Exception as exc:
            self.respond(400,page_shell('Lỗi',"<div class='panel'><h2>Không thể xử lý</h2><p>"+html.escape(str(exc))+"</p><a href='/real-data'>Thử lại</a></div>").encode(),'text/html; charset=utf-8')

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print("SortingLab Dashboard:", url, flush=True)
    print("Đóng cửa sổ này hoặc nhấn Ctrl+C để dừng giao diện.", flush=True)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
