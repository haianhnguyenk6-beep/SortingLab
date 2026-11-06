import unittest
from dashboard.server import reproducibility_manifest, reproducibility_page


class ReproducibilityTests(unittest.TestCase):
    def test_inventory(self):
        manifest = reproducibility_manifest()
        self.assertEqual(len(manifest["dataset_inventory"]), 3)
        self.assertIn("audit", manifest)

    def test_html(self):
        self.assertIn("export-manifest", reproducibility_page())


if __name__ == "__main__":
    unittest.main()
