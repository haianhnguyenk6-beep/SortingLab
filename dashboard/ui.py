"""Shared, offline UI. Navigation groups features without removing old URLs."""
import html
from pathlib import Path

TEMPLATE = Path(__file__).with_name("index.html")
ICONS = {
    "EXPERIMENT": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "DATA": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/>',
    "RUN": '<path d="m9 5 11 7-11 7V5Z"/><path d="M4 5v14"/>',
    "RESULTS": '<path d="M4 3v17h17M8 15v-4M13 15V6M18 15v-7"/>',
    "HISTORY": '<path d="M3 11a9 9 0 1 1 3 8M3 4v7h7M12 7v5l3 2"/>',
    "TOOLS": '<path d="m14 6 4 4M5 19l6-6M20 3a6 6 0 0 0-8 8l-8 8a2 2 0 0 0 3 3l8-8a6 6 0 0 0 8-8l-5 4-4-4 4-5Z"/>',
}
RESULT_VIEWS = {
    "Executive Report": ("overview", "Tổng quan"),
    "Compare": ("compare", "So sánh datasets"),
    "Insights": ("explore", "Lọc số liệu"),
    "Dashboard": ("latest", "Lần chạy mới nhất"),
}


def render_page(title, body):
    section = "tools"
    if title == "Experiment Data":
        section = "experiment"
    elif title in ("CSV", "Chọn cột", "Lỗi"):
        section = "real-data"
    elif title in ("Benchmark All", "Hoàn tất"):
        section = "batch"
    elif title in ("Lịch sử", "Đã xóa lịch sử"):
        section = "history"
    elif title in RESULT_VIEWS:
        section = "results"
        view = RESULT_VIEWS[title][0]
        tabs = "".join(
            '<a class="tab" href="/results?view=' + key + '"'
            + (' aria-current="page"' if key == view else '') + '>' + label + '</a>'
            for key, label in RESULT_VIEWS.values()
        )
        body = ('<div class="page-heading"><div><span class="eyebrow">REAL-LIFE WORKSPACE</span>'
                '<h1>Kết quả benchmark</h1><p>Tổng hợp, so sánh và xuất dữ liệu trong cùng một nơi.</p></div>'
                '<a class="button secondary" href="/batch">Chạy benchmark mới <span aria-hidden="true">↗</span></a></div>'
                '<nav class="tabs" aria-label="Chế độ xem kết quả">' + tabs + '</nav>'
                + body.replace('<h1>', '<h2>', 1).replace('</h1>', '</h2>', 1))
        title = "Kết quả benchmark"
    page = TEMPLATE.read_text(encoding="utf-8")
    # Insert user-derived body last, so its content cannot become template tokens.
    for name, paths in ICONS.items():
        icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + paths + '</svg>'
        page = page.replace("{{ICON_" + name + "}}", icon)
    display_title = 'Real-life Data' if title == 'CSV' else title
    page = page.replace("{{TITLE}}", html.escape(display_title)).replace("{{SECTION}}", section)
    page = page.replace('data-nav="' + section + '"', 'data-nav="' + section + '" aria-current="page"')
    return page.replace("{{BODY}}", body)
