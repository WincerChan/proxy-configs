from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGION_GROUPS = [
    "🇭🇰 香港自动",
    "🇹🇼 台湾自动",
    "🇯🇵 日本自动",
    "🇸🇬 新加坡自动",
    "🇺🇸 美国自动",
    "🇰🇷 韩国自动",
    "🇬🇧 英国自动",
    "🇪🇺 欧洲自动",
    "🇨🇦 加拿大自动",
    "🇦🇺 澳洲自动",
]


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
    def test_ai_offers_all_region_groups_and_manual_node_selection(self):
        paths = {
            "Clash": clash_ai_choices(ROOT / "dist/clash/clash-naixi-stable.yaml"),
            "Quantumult X": quanx_ai_choices(
                ROOT / "dist/quanx/quantumultx-naixi-stable.conf"
            ),
        }
        for client, choices in paths.items():
            with self.subTest(client=client):
                self.assertEqual(choices[0], "🇺🇸 美国自动")
                for group in REGION_GROUPS + ["🧭 节点选择"]:
                    self.assertEqual(choices.count(group), 1, f"{client}: {group}")


if __name__ == "__main__":
    unittest.main()
