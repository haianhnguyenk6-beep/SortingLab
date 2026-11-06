"""Small server-rendered views for the simplified real-data workflow."""
import html


def steps(current):
    labels = ("Chọn dữ liệu", "Cấu hình phép đo", "Xem kết quả")
    return '<ol class="steps" aria-label="Các bước benchmark">' + ''.join(
        '<li' + (' class="current" aria-current="step"' if i == current else '')
        + '><b>' + str(i) + '</b>' + label + '</li>'
        for i, label in enumerate(labels, 1)
    ) + '</ol>'


def real_data_body(datasets):
    rows, options, references = [], [], []
    for key, cfg, present in datasets:
        label = {"superstore": "Superstore Sales", "olist": "Olist E-Commerce", "creditcard": "Credit Card Fraud"}[key]
        rows.append('<div class="dataset-row"><div><b>' + label + '</b><small>'
                    + html.escape(cfg["file"]) + ' · Cột ' + html.escape(cfg["column"])
                    + '</small></div><span class="badge ' + ('good">Sẵn sàng' if present else 'warn">Thiếu CSV') + '</span></div>')
        options.append('<option value="' + key + '"' + ('' if present else ' disabled') + '>' + label + '</option>')
        references.append('<a href="https://www.kaggle.com/datasets/' + cfg['slug'] + '" target="_blank" rel="noopener noreferrer">' + label + ' ↗</a>')
    ready = any(present for _, _, present in datasets)
    return '''<div class="page-heading"><div><span class="eyebrow">REAL-LIFE WORKSPACE</span><h1>Real-life Data</h1><p>Đưa dữ liệu thực tế vào phép đo.<br>Chọn một CSV có sẵn hoặc tải dữ liệu của bạn lên để bắt đầu.</p></div><a class="button secondary" href="/results">Xem kết quả đã lưu ↗</a></div>''' + steps(1) + '''
    <div class="source-grid"><section class="panel"><div class="panel-head"><div><div class="section-index">NGUỒN 01</div><h2>Dữ liệu có sẵn</h2><p>Ba CSV được đóng gói cùng dự án, xử lý ngay trên máy.</p></div><span class="badge">CSV</span></div><div class="dataset-list">''' + ''.join(rows) + '''</div>
    <form class="source-action" action="/use-local-kaggle" method="post"><label class="field" for="local-dataset">Dataset<select id="local-dataset" name="dataset">''' + ''.join(options) + '''</select></label><button type="submit"''' + ('' if ready else ' disabled') + '''>Chọn dữ liệu →</button></form></section>
    <section class="panel"><div class="panel-head"><div><div class="section-index">NGUỒN 02</div><h2>CSV của bạn</h2><p>Tự chọn cột số và kích thước mẫu ở bước tiếp theo.</p></div></div>
    <form class="upload-form" action="/upload" method="post" enctype="multipart/form-data"><div class="upload-zone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V3m-5 5 5-5 5 5M4 16v4h16v-4"/></svg><label for="csv-file">Chọn file dữ liệu trên máy</label><small id="upload-filename">CSV UTF-8 · Tối đa 12 MB</small><input id="csv-file" type="file" name="dataset" accept=".csv,text/csv" required aria-describedby="upload-filename"></div><button type="submit">Đọc cột dữ liệu →</button></form></section></div>
    <div class="note-box"><strong>Chỉ có ba bước.</strong> Chọn CSV → chọn cột số và số phần tử → xem kết quả. Benchmark tổng hợp dành cho việc chạy cả ba bộ dữ liệu; các báo cáo kiểm tra nằm trong Công cụ nâng cao.</div>
    <details class="panel source-details"><summary>Nguồn tham khảo &amp; định dạng CSV</summary><p>CSV có tiêu đề cột, phân tách bằng dấu phẩy và mã hóa UTF-8. Cột benchmark phải chứa số hữu hạn. Giá trị trống hoặc không hợp lệ sẽ được bỏ qua; số dòng thực đo có thể thấp hơn kích thước mẫu yêu cầu.</p><p>Các CSV đi kèm được lấy từ gói dự án bạn cung cấp. Nguồn tải gốc chưa được xác minh độc lập. Trang tham khảo:</p>''' + ''.join(references) + '''</details>'''


def batch_body(datasets):
    cells = ''.join('<tr><td>' + html.escape(cfg['title']) + '</td><td><span class="badge '
                    + ('good">Sẵn sàng' if present else 'warn">Thiếu CSV')
                    + '</span></td><td>' + html.escape(cfg['column']) + '</td></tr>' for _, cfg, present in datasets)
    ready = sum(present for _, _, present in datasets)
    return '''<div class="page-heading"><div><span class="eyebrow">REAL-LIFE WORKSPACE</span><h1>Benchmark All</h1><p>Một lần chạy, so sánh trên cả ba bộ dữ liệu có sẵn.</p></div><a class="button secondary" href="/results">Xem kết quả ↗</a></div>
    <div class="batch-intro"><section class="panel"><h2>Dữ liệu tham gia phép đo</h2><p>Dataset thiếu CSV được báo rõ và bỏ qua; các bộ còn lại vẫn được chạy.</p><div class="tablewrap"><table><thead><tr><th>Dataset</th><th>Trạng thái</th><th>Cột số</th></tr></thead><tbody>''' + cells + '''</tbody></table></div><p class="table-note">Các CSV có sẵn được lấy từ gói dự án. Số phần tử thực đo phụ thuộc số giá trị hợp lệ trong từng tệp.</p></section>
    <section class="panel batch-action"><span class="section-index">CẤU HÌNH TỔNG HỢP</span><h2>Chạy bộ benchmark</h2><div class="batch-specs"><div><strong>6</strong><small>thuật toán</small></div><div><strong>3</strong><small>kích thước mẫu</small></div><div><strong>3</strong><small>lần lặp</small></div></div><p>n = 1.000, 5.000 và 10.000. Tác vụ có thể mất vài phút, đặc biệt với Insertion ở mẫu lớn.</p><form action="/batch-run" method="post"><button type="submit"''' + ('' if ready else ' disabled') + '''>▷ Chạy benchmark tổng hợp</button></form><p class="hint">Kết quả được ghi vào lịch sử và khu Kết quả benchmark.</p></section></div>'''


def selection_body(filename, columns, source, title):
    preferred = next((column for column in columns if column.lower() in ('sales', 'price', 'amount')), columns[0])
    options = ''.join('<option value="' + html.escape(column, quote=True) + '"'
                      + (' selected' if column == preferred else '') + '>' + html.escape(column) + '</option>' for column in columns)
    sizes = ''.join('<option value="' + str(n) + '"' + (' selected' if n == 1000 else '') + '>' + f'{n:,}'.replace(',', '.') + '</option>' for n in (100, 500, 1000, 2000, 4000, 10000, 50000))
    return '<div class="page-heading"><div><span class="eyebrow">REAL-LIFE WORKSPACE</span><h1>Cấu hình phép đo</h1><p>' + html.escape(title) + '</p></div><a class="button secondary" href="/real-data">← Đổi dữ liệu</a></div>' + steps(2) + '''
    <section class="panel selection-form"><h2>Chọn dữ liệu cần sắp xếp</h2><div class="selection-file">''' + html.escape(filename) + '<small>' + str(len(columns)) + ''' cột có giá trị số · 6 thuật toán · 3 lần lặp</small></div>
    <form action="/benchmark" method="post"><input type="hidden" name="source" value="''' + html.escape(source, quote=True) + '''"><label class="field">Cột số<select name="column" required>''' + options + '''</select></label><label class="field">Số phần tử tối đa<select name="limit">''' + sizes + '''</select></label><button type="submit">▷ Chạy benchmark</button></form>
    <p class="table-note">Đọc các giá trị số hợp lệ đầu tiên, tối đa số phần tử bạn chọn. Mẫu từ 10.000 phần tử có thể chạy lâu; Insertion bị bỏ qua khi vượt 10.000 phần tử để giới hạn chi phí.</p></section>'''


def latest_body(available):
    if not available:
        return '<section class="panel empty-state"><h2>Chưa có lần chạy nào</h2><p>Chọn một CSV để tạo kết quả benchmark đầu tiên.</p><a class="button primary" href="/real-data">Chọn dữ liệu →</a></section>'
    return '''<section class="panel"><div class="panel-head"><div><h2>Lần chạy mới nhất</h2><p>Kết quả đo trực tiếp từ CSV bạn đã chọn.</p></div></div><a class="download-btn" href="/export-excel">↓ Tải Excel (.xlsx)</a><a class="button secondary" href="/export">↓ Tải CSV</a><a class="button secondary" href="/powerbi-guide">Hướng dẫn Power BI ↗</a></section><section class="panel"><iframe title="Dashboard kết quả benchmark mới nhất" src="/report"></iframe></section>'''


def tools_body():
    groups = (
        ('01', 'Kiểm tra dữ liệu', 'Kiểm tra đầu vào và các tệp cần thiết trước khi chạy.', (
            ('/quality', 'Data Quality', 'Cột số, giá trị thiếu và giá trị không hợp lệ'),
            ('/readiness', 'Project Readiness', 'Tình trạng CSV và tệp kết quả'))),
        ('02', 'Kiểm tra kết quả', 'Đánh giá chất lượng các phép đo đã được ghi lại.', (
            ('/audit', 'Experiment Audit', 'Số lần chạy, thuật toán và kích thước'),
            ('/validation', 'Experiment Validation', 'Tính hợp lệ và khả năng so sánh'),
            ('/powerbi-health', 'Power BI Health', 'Định dạng và dữ liệu trong tệp xuất'))),
        ('03', 'Tái lập & bàn giao', 'Giữ thông tin nguồn và đóng gói bằng chứng khi cần nộp bài.', (
            ('/reproducibility', 'Reproducibility', 'Môi trường, nguồn dữ liệu và SHA-256'),
            ('/submission', 'Submission Center', 'Gói ZIP gồm CSV, manifest và DAX'))),
    )
    body = '<div class="page-heading tools-heading"><div><span class="eyebrow">CÔNG CỤ NÂNG CAO</span><h1>Kiểm tra &amp; bàn giao</h1><p>Các công cụ chuyên sâu được gom theo mục đích. Mở khi cần kiểm tra hoặc chuẩn bị báo cáo.</p></div></div><div class="tools-grid">'
    for number, title, description, tools in groups:
        body += '<section class="panel tool-card"><span class="section-index">' + number + '</span><h2>' + html.escape(title) + '</h2><p>' + description + '</p>'
        for url, label, detail in tools:
            body += '<a class="tool-link" href="' + url + '"><span>' + label + '<small>' + html.escape(detail) + '</small></span><span aria-hidden="true">↗</span></a>'
        body += '</section>'
    return body + '</div>'
