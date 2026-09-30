from pathlib import Path
import re
import unittest

from test_quanx_policy import load_static_policies


ROOT = Path(__file__).resolve().parents[1]


class QuanXRelayTests(unittest.TestCase):
    def test_relay_candidates_exclude_landing_nodes(self):
        samples = {
            "🧭 节点选择": "JP 01",
            "♻️ 自动低延迟": "JP 01",
            "🛟 故障切换": "JP 01",
            "🇭🇰 香港自动": "HK 01",
            "🇹🇼 台湾自动": "TW 01",
            "🇯🇵 日本自动": "JP 01",
            "🇸🇬 新加坡自动": "SG 01",
            "🇺🇸 美国自动": "US 01",
            "🇰🇷 韩国自动": "KR 01",
            "🇬🇧 英国自动": "UK 01",
            "🇪🇺 欧洲自动": "Germany 01",
            "🇨🇦 加拿大自动": "Canada 01",
            "🇦🇺 澳洲自动": "AU 01",
        }
        for path in [ROOT / "src/quanx/20-policy.conf",
                     ROOT / "dist/quanx/quantumultx-naixi-stable.conf"]:
            policies = load_static_policies(path)
            self.assertEqual(set(policies["♾️ 中转"]), set(samples))
            for group, sample in samples.items():
                with self.subTest(path=path, group=group):
                    line = next(line for line in path.read_text().splitlines()
                                if f" = {group}," in line)
                    pattern = line.split("server-tag-regex=", 1)[1].split(", check-interval=", 1)[0]
                    self.assertIsNotNone(re.search(pattern, sample))
                    for node in ["land-jp", "LAND-JP", "land-" + sample,
                                 "LaNd-" + sample, "Premium " + sample]:
                        self.assertIsNone(re.search(pattern, node), node)
            self.assertEqual(policies["🤖 AI"], ["land-jp"])

    def test_ai_rules_use_landing_node_and_tun(self):
        for base in [ROOT / "src/quanx", ROOT / "dist/quanx"]:
            with self.subTest(base=base):
                def read(part):
                    path = base / (part if base.name == "quanx" and base.parent.name == "src"
                                   else "quantumultx-naixi-stable.conf")
                    return path.read_text()

                policies = read("20-policy.conf")
                ai_policy = next(line for line in policies.splitlines()
                                 if line.startswith("static = 🤖 AI,"))
                self.assertEqual(ai_policy, "static = 🤖 AI, land-jp")
                rules = read("70-filter-local.conf").split("[filter_local]", 1)[1]
                rules = rules.split("\n[", 1)[0].splitlines()
                ai_rules = [line for line in rules if ", 🤖 AI" in line]
                self.assertGreater(len(ai_rules), 0)
                self.assertTrue(all(line.endswith(", 🤖 AI, via-interface=%TUN%")
                                    for line in ai_rules))
                self.assertFalse(any("via-interface" in line for line in rules
                                     if ", 🤖 AI" not in line))
                remote = next(line for line in read("50-filter-remote.conf").splitlines()
                              if "force-policy=🤖 AI" in line)
                self.assertIn("category-ai-!cn.list#type=domain-set&via=%TUN%", remote)
                self.assertIn("opt-parser=true", remote)
                self.assertIn("resource_parser_url = https://raw.githubusercontent.com/"
                              "KOP-XIAO/QuantumultX/master/Scripts/resource-parser.js",
                              read("00-general.conf"))

    def test_landing_domain_routes_to_independent_relay_group(self):
        for policy_path, filter_path in [
            (ROOT / "src/quanx/20-policy.conf", ROOT / "src/quanx/70-filter-local.conf"),
            (ROOT / "dist/quanx/quantumultx-naixi-stable.conf",) * 2,
        ]:
            with self.subTest(path=filter_path):
                policies = load_static_policies(policy_path)
                choices = policies["♾️ 中转"]
                self.assertEqual(choices[0], "🇯🇵 日本自动")
                self.assertIn("🧭 节点选择", choices)
                self.assertTrue(all(
                    choice.endswith("自动") or choice in {
                        "🧭 节点选择", "♻️ 自动低延迟", "🛟 故障切换"
                    }
                    for choice in choices
                ))
                local_rules = filter_path.read_text().split("[filter_local]", 1)[1]
                local_rules = local_rules.split("\n[", 1)[0]
                rules = [
                    line.strip() for line in local_rules.splitlines()
                    if line.strip() and not line.lstrip().startswith(("#", ";"))
                ]
                self.assertEqual(rules[0], "host-suffix, land.itswincer.net, ♾️ 中转")


if __name__ == "__main__":
    unittest.main()
