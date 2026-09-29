from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOMAINS = {
    "hound-jp.itswincer.net",
    "hound-robin-jp.itswincer.net",
    "arc-jp.hound.itswincer.net",
}
GROUP = "🐕 Hound"


class HoundGroupTests(unittest.TestCase):
    def test_clash_group_and_exact_domain_rules(self):
        config = (ROOT / "dist/clash/clash-naixi-stable.yaml").read_text(
            encoding="utf-8"
        )
        group = config.split(f"- name: {GROUP}\n", 1)[1].split("- name: ", 1)[0]
        self.assertIn("  type: select\n", group)
        self.assertIn("  - 🇯🇵 日本自动\n", group)
        self.assertIn("  - 🧭 节点选择\n", group)

        rules = {
            line.removeprefix("- DOMAIN,").split(",", 1)[0]
            for line in config.splitlines()
            if line.startswith("- DOMAIN,") and line.endswith(f",{GROUP}")
        }
        self.assertEqual(rules, DOMAINS)

    def test_quanx_group_and_exact_host_rules(self):
        config = (ROOT / "dist/quanx/quantumultx-naixi-stable.conf").read_text(
            encoding="utf-8"
        )
        policy = next(
            line for line in config.splitlines() if line.startswith(f"static = {GROUP}, ")
        )
        choices = [part.strip() for part in policy.split(",")[1:]]
        self.assertEqual(choices[0], "🇯🇵 日本自动")
        self.assertIn("🧭 节点选择", choices)

        hosts = {
            line.removeprefix("host, ").split(",", 1)[0]
            for line in config.splitlines()
            if line.startswith("host, ") and line.endswith(f", {GROUP}")
        }
        self.assertEqual(hosts, DOMAINS)


if __name__ == "__main__":
    unittest.main()
