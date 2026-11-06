import tempfile
import unittest
from pathlib import Path
from acceptance.verify_v23 import csv_stats, sha256, collect


class AcceptanceTests(unittest.TestCase):
    def test_valid_numeric_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'sample.csv'
            p.write_text('Sales\n10\n12.5\n', encoding='utf-8')
            result = csv_stats(p, 'Sales')
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['valid_numeric'], 2)
            self.assertEqual(len(sha256(p)), 64)

    def test_missing_column_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'sample.csv'
            p.write_text('Other\n5\n', encoding='utf-8')
            self.assertEqual(csv_stats(p, 'Sales')['status'], 'FAIL')

    def test_empty_csv_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'sample.csv'
            p.write_text('Sales\n', encoding='utf-8')
            self.assertEqual(csv_stats(p, 'Sales')['status'], 'FAIL')

    def test_manual_checks_not_falsely_passed(self):
        checks = collect(run_tests=False)
        manual = [r for r in checks if r['area'] in ('Windows', 'Power BI')]
        self.assertEqual(len(manual), 2)
        self.assertTrue(all(r['status'] == 'NOT TESTED' for r in manual))


if __name__ == '__main__':
    unittest.main()
