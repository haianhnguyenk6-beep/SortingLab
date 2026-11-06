import csv
import tempfile
import unittest
from pathlib import Path
from acceptance.report_v24 import measured_rows, build


class ReportV24Tests(unittest.TestCase):
    def test_missing_batch(self):
        with tempfile.TemporaryDirectory() as d:
            rows, error = measured_rows(Path(d) / "missing.csv")
            self.assertEqual(rows, [])
            self.assertIn("missing", error)

    def test_filter_invalid_benchmark_rows(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "batch.csv"
            with path.open("w", newline="") as f:
                w = csv.DictWriter(
                    f, fieldnames=["dataset", "algorithm", "n", "median_ms", "status"])
                w.writeheader()
                w.writerow(dict(dataset="superstore", algorithm="merge",
                           n=100, median_ms=1.2, status="ok"))
                w.writerow(dict(dataset="superstore", algorithm="merge",
                           n=100, median_ms=-1, status="ok"))
                w.writerow(dict(dataset="olist", algorithm="heap",
                           n=100, median_ms=0.3, status="error"))
            rows, err = measured_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(err, "")

    def test_report_does_not_claim_unverified_kaggle(self):
        with tempfile.TemporaryDirectory() as d:
            summary = build(run_tests=False, output=Path(d))
            self.assertFalse(summary["original_kaggle_verified"])
            self.assertTrue((Path(d) / "v24_report.html").is_file())
            self.assertEqual(summary["native_powerbi_pbix_validation"], "NOT TESTED")


if __name__ == "__main__":
    unittest.main()
