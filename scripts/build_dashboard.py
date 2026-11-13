"""Create a standalone offline dashboard from the benchmark CSV."""
import argparse,csv,html,math
from pathlib import Path

def build(source, target):
    with open(source, encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = [name for name in ('algorithm', 'median_ms', 'status')
                   if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError('CSV thiếu cột kết quả benchmark: ' + ', '.join(missing))
        rows = list(reader)
    clean=[]
    for r in rows:
        if r.get("status")!="ok":continue
        try:
            ms=float(r["median_ms"])
            mem=float(r["peak_kb"]) if r.get("peak_kb") not in ("",None) else None
            if not math.isfinite(ms) or ms < 0: continue
            if mem is not None and (not math.isfinite(mem) or mem < 0): continue
        except (ValueError,TypeError,KeyError):continue
        clean.append({"algorithm":r["algorithm"],"median_ms":ms,"peak_kb":mem,"n":r.get("n",""),"dataset":r.get("dataset","")})
    clean.sort(key=lambda x:x["median_ms"])
    maxms=max((x["median_ms"] for x in clean),default=1) or 1
    bars="".join(f'<div class="item"><span>{html.escape(x["algorithm"])}</span><div class="track"><div class="bar" style="width:{100*x["median_ms"]/maxms:.2f}%"></div></div><strong>{x["median_ms"]:.4f} ms</strong></div>' for x in clean)
    memory_text=lambda v: f"{v:.2f}" if v is not None else "—"
    trs="".join(f'<tr><td>{html.escape(x["algorithm"])}</td><td>{x["median_ms"]:.6f}</td><td>{memory_text(x["peak_kb"])}</td><td>{html.escape(str(x["n"]))}</td></tr>' for x in clean)
    dataset=html.escape(clean[0]["dataset"] if clean else "No successful benchmark")
    page='<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sorting Lab | Benchmark Dashboard</title><style>body{font-family:system-ui,Arial;background:#0b1220;color:#e8eef9;max-width:1050px;margin:30px auto;padding:20px}h1{color:#8fd3ff}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:#17253b;padding:20px;border-radius:14px;flex:1;min-width:180px}.item{display:grid;grid-template-columns:155px 1fr 110px;gap:14px;align-items:center;margin:14px 0}.track{height:24px;background:#25374e;border-radius:7px;overflow:hidden}.bar{height:100%;background:linear-gradient(90deg,#27a8df,#8c70ff)}table{width:100%;border-collapse:collapse;margin-top:18px}td,th{border-bottom:1px solid #30445e;padding:10px;text-align:left}small{color:#9fb2ce}</style></head><body><h1>Sorting Lab · Benchmark Dashboard</h1><p>Dataset: {{DATASET}}</p><section class="cards"><div class="card"><small>Successful algorithms</small><h2>{{COUNT}}</h2></div><div class="card"><small>Fastest algorithm</small><h2>{{FASTEST}}</h2></div><div class="card"><small>Fastest runtime</small><h2>{{FASTEST_MS}} ms</h2></div></section><h2>Median runtime comparison</h2>{{BARS}}<h2>Detailed measurements</h2><table><thead><tr><th>Algorithm</th><th>Median (ms)</th><th>Peak memory (KB)</th><th>n</th></tr></thead><tbody>{{ROWS}}</tbody></table><p><small>Measurements are machine-specific. Dataset provenance must be checked in the metadata JSON. This is an offline HTML dashboard, not a Power BI .pbix file.</small></p></body></html>'
    page=page.replace("{{DATASET}}",dataset).replace("{{COUNT}}",str(len(clean))).replace("{{FASTEST}}",html.escape(clean[0]["algorithm"] if clean else "N/A")).replace("{{FASTEST_MS}}",f'{clean[0]["median_ms"]:.4f}' if clean else "N/A").replace("{{BARS}}",bars).replace("{{ROWS}}",trs)
    excluded = [r for r in rows if r.get('status') not in ('ok', '', None)]
    if excluded:
        details = ''.join('<tr><td>' + html.escape(str(r.get('algorithm', '')))
                          + '</td><td>' + html.escape(str(r.get('status', '')))
                          + '</td><td>' + html.escape(str(r.get('reason', '')))
                          + '</td></tr>' for r in excluded)
        notice = ('<h2>Phép đo bị bỏ qua hoặc không hoàn tất</h2><table>'
                  '<tr><th>Algorithm</th><th>Status</th><th>Reason</th></tr>'
                  + details + '</table>')
        page = page.replace('</table><p><small>', '</table>' + notice + '<p><small>', 1)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(page,encoding="utf-8")
    return target

def main(argv=None):
    parser = argparse.ArgumentParser(description='Tạo báo cáo HTML từ kết quả benchmark CSV.')
    parser.add_argument('--csv', type=Path, default=Path('results/powerbi/final_benchmark.csv'))
    parser.add_argument('--out', type=Path, default=Path('results/powerbi/FINAL_DASHBOARD.html'))
    args = parser.parse_args(argv)
    if not args.csv.is_file():
        parser.error(
            f'Chưa có CSV kết quả: {args.csv}. Chạy benchmark trong Real-life Data '
            'trước, hoặc truyền --csv với đường dẫn kết quả đã có.'
        )
    try:
        target = build(args.csv, args.out)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        parser.error(str(exc))
    print(target)
    return 0


if __name__ == '__main__':
    main()
