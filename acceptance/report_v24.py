"""Generate a transparent, offline submission-readiness report from actual files."""
import csv
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from acceptance.verify_v23 import ROOT, collect

OUTPUT = ROOT / "evidence"
BATCH = ROOT / "results" / "powerbi" / "all_datasets_benchmark.csv"
REQUIRED = {"dataset", "algorithm", "n", "median_ms", "status"}


def measured_rows(path=BATCH):
    """Return only successful, finite, nonnegative measured benchmark rows."""
    if not path.is_file():
        return [], "Batch benchmark CSV is missing"
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not REQUIRED.issubset(reader.fieldnames or []):
                return [], "Missing required benchmark columns"
            import math
            valid = []
            for row in reader:
                try:
                    n = int(row["n"])
                    ms = float(row["median_ms"])
                    if row["status"].lower() == "ok" and n > 0 and math.isfinite(ms) and ms >= 0:
                        valid.append({"dataset": row["dataset"], "algorithm": row["algorithm"], "n": n, "median_ms": ms})
                except (ValueError, TypeError, KeyError):
                    continue
            return valid, ""
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], str(exc)


def build(run_tests=False, output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    checks = collect(run_tests=run_tests)
    measured, error = measured_rows()
    original = {"superstore", "olist", "creditcard"}
    available = {r["dataset"].lower() for r in measured}
    # Demo results in final_benchmark.csv never qualify as real Kaggle evidence.
    missing = sorted(original - available)
    integrity_passed = not missing and not error and all(
        c["status"] == "PASS" for c in checks if c["area"] == "Kaggle"
    )
    # CSV contents and matching hashes do not establish the original download.
    # The supplied package explicitly says its provenance is not independently verified.
    verified = False
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "original_kaggle_verified": verified,
        "local_csv_integrity_passed": integrity_passed,
        "provenance_note": "User-supplied CSVs; original Kaggle download not independently verified.",
        "datasets_with_measured_batch_results": sorted(available & original),
        "missing_dataset_benchmarks": missing,
        "valid_measured_rows": len(measured),
        "batch_error": error,
        "checks": checks,
        "manual_windows_validation": "NOT TESTED",
        "native_powerbi_pbix_validation": "NOT TESTED",
    }
    (output / "v24_report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    tr = "".join("<tr>" + "".join("<td>" + html.escape(str(c.get(k, ""))) + "</td>" for k in ("area", "check", "status", "reason")) + "</tr>" for c in checks)
    measured_html = "".join("<tr>" + "".join("<td>" + html.escape(str(r[k])) + "</td>" for k in ("dataset", "algorithm", "n", "median_ms")) + "</tr>" for r in measured[:250])
    status = "READY FOR DATA REVIEW" if verified else "NOT FULLY ACCEPTED"
    document = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>SortingLab V24 Acceptance Report</title>
<style>body{{font:15px system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 18px;color:#172033}}h1{{color:#16416e}}table{{border-collapse:collapse;width:100%;margin:14px 0 32px}}td,th{{border:1px solid #cbd5e1;padding:8px;text-align:left}}th{{background:#eaf1f9}}.warn{{font-weight:bold;color:#9a3412}}@media print{{body{{margin:8mm}}}}</style></head><body>
<h1>SortingLab V24 – Acceptance & Evidence Report</h1><p>Generated UTC: {html.escape(summary['created_utc'])}</p>
<p class="warn">Status: {status}. Windows and native Power BI validation are NOT TESTED.</p>
<p>Original Kaggle datasets with valid measured batch rows: {html.escape(', '.join(sorted(available & original)) or 'none')}.</p>
<p>Missing measured datasets: {html.escape(', '.join(missing) or 'none')}. Valid benchmark rows: {len(measured)}.</p>
<p>Batch file: {html.escape(error or 'readable')}. Demo CSVs do not count as Kaggle evidence.</p>
<h2>Acceptance checks</h2><table><tr><th>Area</th><th>Check</th><th>Status</th><th>Reason</th></tr>{tr}</table>
<h2>Measured batch rows (first 250)</h2><table><tr><th>Dataset</th><th>Algorithm</th><th>n</th><th>Median (ms)</th></tr>{measured_html}</table>
<h2>Manual sign-off</h2><p>Windows launcher: __________ Date: __________ Evidence: __________</p><p>Power BI Desktop .pbix: __________ Date: __________ Evidence: __________</p></body></html>"""
    (output / "v24_report.html").write_text(document, encoding="utf-8")
    return summary

if __name__ == "__main__":
    summary = build(run_tests=True)
    print("V24 report created: evidence/v24_report.html and evidence/v24_report.json")
    print("Kaggle verified:", summary["original_kaggle_verified"])
    print("Missing dataset benchmarks:", ", ".join(summary["missing_dataset_benchmarks"]) or "none")
