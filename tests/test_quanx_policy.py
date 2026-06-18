from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BUSINESS_POLICIES = [
    "🇭🇰 香港自动",
    "🇹🇼 台湾自动",
    "🇺🇸 美国自动",
    "🇯🇵 日本自动",
    "🇸🇬 新加坡自动",
    "♻️ 自动低延迟",
    "🛟 故障切换",
    "🚀 代理",
]
NON_BUSINESS_POLICIES = {
    "🚀 代理",
    "🧭 节点选择",
    "📊 流量看板",
    "🇨🇳 直连",
    "🐟 Final",
}


def load_static_policies(path: Path) -> dict[str, list[str]]:
    policies = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("static = "):
            continue

        parts = [part.strip() for part in line.removeprefix("static = ").split(",")]
        if len(parts) < 2:
            continue
        policies[parts[0]] = parts[1:]
    return policies


class QuanXPolicyTests(unittest.TestCase):
    def test_business_policies_include_required_choices(self):
        policies = load_static_policies(
            ROOT / "dist" / "quanx" / "quantumultx-naixi-stable.conf"
        )

        business_policies = {
            name: choices
            for name, choices in policies.items()
            if name not in NON_BUSINESS_POLICIES
            and any(choice in choices for choice in REQUIRED_BUSINESS_POLICIES)
        }
        self.assertIn("🤖 AI", business_policies)
        self.assertIn("🌍 Global", business_policies)

        for name, choices in business_policies.items():
            with self.subTest(policy=name):
                for required_policy in REQUIRED_BUSINESS_POLICIES:
                    self.assertIn(required_policy, choices)


if __name__ == "__main__":
    unittest.main()
