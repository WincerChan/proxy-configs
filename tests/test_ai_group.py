from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

def clash_ai_choices(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index("- name: 🤖 AI")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("- name: "))
    return [line.removeprefix("  - ") for line in lines[start:end] if line.startswith("  - ")]


def quanx_ai_choices(path: Path) -> list[str]:
    line = next(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("static = 🤖 AI, ")
    )
    return [choice.strip() for choice in line.removeprefix("static = 🤖 AI, ").split(",")]


class AiGroupTests(unittest.TestCase):
    def test_clash_relay_selects_nodes_without_nested_groups(self):
        for path in [ROOT / "src/clash/20-proxy-groups.yaml",
                     ROOT / "dist/clash/clash-naixi-stable.yaml"]:
            with self.subTest(path=path):
                text = path.read_text()
                relay = text.split("- name: ♾️ 中转\n", 1)[1].split("- name:", 1)[0]
                self.assertIn("  type: select\n", relay)
                self.assertIn("  include-all-proxies: true\n", relay)
                self.assertNotIn("  proxies:", relay)
                self.assertNotIn("  use:", relay)
                self.assertNotIn("include-all:", relay)

    def test_quanx_ai_uses_dedicated_landing_node(self):
        self.assertEqual(
            quanx_ai_choices(ROOT / "dist/quanx/quantumultx-naixi-stable.conf"),
            ["land-jp"],
        )

    def test_clash_ai_uses_dedicated_landing_node(self):
        for path in [ROOT / "src/clash/20-proxy-groups.yaml",
                     ROOT / "dist/clash/clash-naixi-stable.yaml"]:
            with self.subTest(path=path):
                self.assertEqual(clash_ai_choices(path), ["land-jp"])


if __name__ == "__main__":
    unittest.main()
