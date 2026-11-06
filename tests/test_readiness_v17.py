import unittest
from dashboard.server import readiness_report, readiness_page


class ReadinessTests(unittest.TestCase):
    def test_six_checks(self):
        rows = readiness_report()
        self.assertEqual(len(rows), 6)
        self.assertEqual({x['status'] for x in rows} - {'READY', 'MISSING'}, set())

    def test_navigation(self):
        self.assertIn('export-readiness', readiness_page())
        self.assertIn('Project Readiness', readiness_page())
