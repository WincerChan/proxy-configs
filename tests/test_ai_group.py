from pathlib import Path
import unittest

from test_validate_clash import load_validate_clash

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
    def test_clash_relay_uses_only_airport_selection_groups(self):
        validator = load_validate_clash()
        for path in [ROOT / "src/clash/20-proxy-groups.yaml",
                     ROOT / "dist/clash/clash-naixi-stable.yaml"]:
            with self.subTest(path=path):
                _, groups = validator.load_structure(path)
                choices = groups["♾️ 中转"]
                self.assertEqual(choices[0], "🇯🇵 日本自动")
                self.assertIn("🧭 节点选择", choices)
                for choice in choices:
                    self.assertIn(choice, groups)
                    self.assertTrue(choice.endswith("自动") or choice in {
                        "🧭 节点选择", "♻️ 自动低延迟", "🛟 故障切换"
                    })

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
