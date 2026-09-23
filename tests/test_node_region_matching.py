from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "🇺🇸 美国自动": {
        "included": ["🇺🇸 USA Los Angeles 07", "US 01", "US01"],
        "excluded": [
            "🇷🇺 Russia St. Petersburg",
            "🇷🇺 Russia Moscow 01",
            "🇦🇹 Austria 01",
            "🇦🇺 Australia Sydney 02",
        ],
    },
    "🇦🇺 澳洲自动": {
        "included": ["🇦🇺 Australia Sydney 02", "AU 01", "AU01"],
        "excluded": ["🇦🇹 Austria 01", "🇷🇺 Russia Moscow 01"],
    },
}


def clash_filters(path: Path) -> dict[str, str]:
    filters = {}
    current_group = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- name: "):
            current_group = line.removeprefix("- name: ")
        elif current_group in CASES and line.startswith("  filter: "):
            filters[current_group] = line.removeprefix("  filter: ")
    return filters


def quanx_filters(path: Path) -> dict[str, str]:
    filters = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("url-latency-benchmark = "):
            continue
        group = line.split(",", 1)[0].removeprefix("url-latency-benchmark = ")
        if group in CASES:
            filters[group] = line.split("server-tag-regex=", 1)[1].split(", check-interval=", 1)[0]
    return filters


class NodeRegionMatchingTests(unittest.TestCase):
    def test_country_filters_do_not_match_substrings_in_other_countries(self):
        paths = {
            "Clash": clash_filters(ROOT / "dist/clash/clash-naixi-stable.yaml"),
            "Quantumult X": quanx_filters(
                ROOT / "dist/quanx/quantumultx-naixi-stable.conf"
            ),
        }
        for client, filters in paths.items():
            for group, cases in CASES.items():
                self.assertIn(group, filters, f"{client}: missing {group}")
                pattern = re.compile(filters[group])
                for node in cases["included"]:
                    with self.subTest(client=client, group=group, node=node):
                        self.assertIsNotNone(pattern.search(node))
                for node in cases["excluded"]:
                    with self.subTest(client=client, group=group, node=node):
                        self.assertIsNone(pattern.search(node))


if __name__ == "__main__":
    unittest.main()
