import json
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.tree = json.loads((ROOT / "config" / "tree.json").read_text())

    def _walk(self, node, acc):
        acc.append(node["title"])
        for child in node.get("children") or []:
            self._walk(child, acc)
        return acc

    def test_unique_service_titles(self):
        titles = self._walk(self.tree["root"], [])
        self.assertEqual(len(titles), len(set(titles)), titles)

    def test_root_is_tamm(self):
        self.assertEqual(self.tree["root"]["title"], "TAMM")


class CatalogTests(unittest.TestCase):
    def test_kpi_titles_exist_in_tree(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from itsi_lab.kpis import catalog
        from itsi_lab.tree import load_tree

        titles = []

        def walk(node):
            titles.append(node["title"])
            for child in node.get("children") or []:
                walk(child)

        walk(load_tree()["root"])
        missing = [name for name in catalog() if name not in titles]
        self.assertEqual(missing, [])


class SampleTests(unittest.TestCase):
    def test_channels_and_window(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from itsi_lab.samples import generate

        now = datetime(2026, 10, 12, 12, 0, 0)
        events = generate(now)
        channels = {ev["channel"] for ev in events}
        expected = {
            "call_center",
            "survey",
            "social_media",
            "snow",
            "revenue",
            "uaepass",
            "authentication",
            "appdynamics",
            "azure",
            "kubernetes",
            "database",
            "ad_connect",
        }
        self.assertTrue(expected.issubset(channels), channels)
        self.assertGreater(len(events), 1000)
        times = [ev["time"] for ev in events]
        self.assertGreaterEqual((now - min(times)).total_seconds(), 23 * 3600)
        self.assertLessEqual((now - max(times)).total_seconds(), 200)


if __name__ == "__main__":
    unittest.main()
