from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClashLocalNodeTests(unittest.TestCase):
    def test_groups_discover_local_nodes_without_provider(self):
        for path in [ROOT / "src/clash/20-proxy-groups.yaml",
                     ROOT / "dist/clash/clash-naixi-stable.yaml"]:
            with self.subTest(path=path):
                text = path.read_text()
                self.assertNotIn("  use:", text)
                self.assertNotIn("proxy-providers:", text)
                groups = text.split("- name: ")[1:]
                dynamic = [group for group in groups if "  filter:" in group]
                self.assertEqual(len(dynamic), 14)
                for group in dynamic:
                    name = group.splitlines()[0]
                    self.assertIn("  include-all-proxies: true", group, name)
                    if name == "📊 流量看板":
                        continue
                    self.assertIn("  exclude-filter: ", group, name)
                    exclusion = group.split("  exclude-filter: ", 1)[1]
                    lines = exclusion.splitlines()
                    pattern = lines[0]
                    for line in lines[1:]:
                        if not line.startswith("    "):
                            break
                        pattern += " " + line.strip()
                    for node in ["land-jp", "land-us", "LAND-JP"]:
                        self.assertIsNotNone(re.search(pattern, node), name)
                    self.assertIsNone(re.search(pattern, "Japan JP 01"), name)


if __name__ == "__main__":
    unittest.main()
