import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import yaml

from test_build_release import ROOT, load_build_release


class LatchConfigTests(unittest.TestCase):
    def setUp(self):
        self.build = load_build_release()
        self.document = self.build.latch_document()

    def target(self, rule_prefix):
        rule = next(rule for rule in self.document["rules"] if rule.startswith(rule_prefix + ","))
        return rule.split(",")[2]

    def test_daily_default_routes_and_chain(self):
        self.assertEqual("🤖 AI", self.target("DOMAIN-SUFFIX,chatgpt.com"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,binance.com"))
        self.assertEqual("🇸🇬 新加坡自动", self.target("RULE-SET,telegram_domain"))
        self.assertEqual("🇯🇵 日本自动", self.target("DOMAIN,hound-jp.itswincer.net"))
        self.assertEqual("DIRECT", self.target("RULE-SET,apple"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,push.apple.com"))
        self.assertEqual("DIRECT", self.target("DOMAIN-SUFFIX,steamcontent.com"))
        self.assertEqual("DIRECT", self.target("DOMAIN-SUFFIX,store.steampowered.com"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,steamcommunity.com"))
        self.assertEqual([{"name": "land-jp", "dialer-proxy": "♾️ 中转"}], self.document["proxies"])

    def test_matching_excludes_landing_premium_and_information(self):
        groups = {group["name"]: group for group in self.document["proxy-groups"]}
        relay = re.compile(groups["♾️ 中转"]["filter"], re.IGNORECASE)
        japan = re.compile(groups["🇯🇵 日本自动"]["filter"], re.IGNORECASE)
        for name in ["JP 01", "Tokyo 02", "日本 03"]:
            self.assertTrue(relay.search(name), name)
            self.assertTrue(japan.search(name), name)
        for name in ["land-jp", "LAND-JP", "JP Premium", "JP [Premium]", "剩余流量 JP", "Expire Date JP", "1 GB | 20 GB"]:
            self.assertFalse(relay.search(name), name)
            self.assertFalse(japan.search(name), name)
        self.assertFalse(japan.search("HK 01"))
        ai = re.compile(groups["🤖 AI"]["filter"], re.IGNORECASE)
        self.assertTrue(ai.search("land-jp"))
        self.assertFalse(ai.search("JP 01"))

    def test_providers_and_rule_options_preserve_source(self):
        source = yaml.safe_load((ROOT / "src/clash/30-rule-providers.yaml").read_text())["rule-providers"]
        providers = self.document["rule-providers"]
        self.assertEqual(set(source), set(providers))
        for name, provider in providers.items():
            self.assertEqual("yaml", provider["format"])
            self.assertEqual(source[name]["behavior"], provider["behavior"])
            self.assertEqual(source[name]["interval"], provider["interval"])
            self.assertNotIn("proxy", provider)
            self.assertFalse(provider["path"].endswith(".mrs"))
        self.assertTrue(providers["apple"]["url"].endswith("/Apple_Classical.yaml"))
        source_rules = yaml.safe_load((ROOT / "src/clash/40-rules.yaml").read_text())["rules"]
        self.assertEqual(len(source_rules), len(self.document["rules"]))
        for original, adapted in zip(source_rules, self.document["rules"]):
            left, right = original.split(","), adapted.split(",")
            index = 1 if left[0] == "MATCH" else 2
            self.assertEqual(left[:index], right[:index])
            self.assertEqual(left[index + 1:], right[index + 1:])

    def test_policy_override_and_invalid_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            profile = root / "src/latch/profile.json"
            settings = json.loads(profile.read_text())
            settings["policyTargets"]["✈️ Telegram"] = "🇯🇵 日本自动"
            profile.write_text(json.dumps(settings))
            result = self.build.latch_document(root)
            self.assertIn("RULE-SET,telegram_domain,🇯🇵 日本自动", result["rules"])
            settings["policyTargets"]["✈️ Telegram"] = "invented-policy"
            profile.write_text(json.dumps(settings))
            with self.assertRaisesRegex(ValueError, "Invalid policy choice"):
                self.build.latch_document(root)

    def test_real_node_credentials_do_not_enter_routing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            node_path = root / "src/clash/10-proxies.yaml"
            node_path.write_text(yaml.safe_dump({"proxies": [{"name": "land-jp", "type": "trojan", "server": "secret.example", "port": 443, "password": "credential-sentinel"}]}))
            artifact = json.dumps(self.build.latch_document(root))
            self.assertNotIn("credential-sentinel", artifact)
            self.assertNotIn("secret.example", artifact)

    def test_policy_and_chain_cycles_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            group_path = root / "src/clash/20-proxy-groups.yaml"
            original = group_path.read_text()
            groups = yaml.safe_load(original)
            proxy = next(group for group in groups["proxy-groups"] if group["name"] == "🚀 代理")
            proxy["proxies"] = ["🐟 Final"]
            group_path.write_text(yaml.safe_dump(groups, allow_unicode=True))
            with self.assertRaisesRegex(ValueError, "Policy cycle"):
                self.build.latch_document(root)
            group_path.write_text(original)
            profile = root / "src/latch/profile.json"
            settings = json.loads(profile.read_text())
            settings["chains"]["land-jp"] = "land-jp"
            profile.write_text(json.dumps(settings))
            with self.assertRaisesRegex(ValueError, "Chain cycle"):
                self.build.latch_document(root)

    def test_unknown_mrs_origin_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            provider_path = root / "src/clash/30-rule-providers.yaml"
            data = yaml.safe_load(provider_path.read_text())
            data["rule-providers"]["ai_domain"]["url"] = "https://unverified.invalid/ai.mrs"
            provider_path.write_text(yaml.safe_dump(data, allow_unicode=True))
            with self.assertRaisesRegex(ValueError, "No verified YAML equivalent"):
                self.build.latch_document(root)


if __name__ == "__main__":
    unittest.main()
