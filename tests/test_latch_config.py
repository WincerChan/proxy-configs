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
        kind, value = rule_prefix.split(',', 1)
        for policy in self.document['policy-groups']:
            if any(line.split(',')[:2] == [kind, value] for line in policy.get('conditions', [])):
                return policy['target']
            for ref in policy['rule-sets']:
                if kind == 'RULE-SET' and ref == value:
                    return policy['target']
                provider = self.document['rule-providers'][ref]
                if provider['type'] == 'inline' and any(line.split(',')[:2] == [kind, value] for line in provider['payload']):
                    return policy['target']
        self.fail(f'Missing rule: {rule_prefix}')

    def test_daily_default_routes_and_chain(self):
        self.assertEqual("land-jp", self.target("DOMAIN-SUFFIX,chatgpt.com"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,binance.com"))
        self.assertEqual("🇸🇬 新加坡自动", self.target("RULE-SET,telegram_domain"))
        self.assertEqual("🇯🇵 日本自动", self.target("DOMAIN,hound-jp.itswincer.net"))
        self.assertEqual("DIRECT", self.target("RULE-SET,apple"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,push.apple.com"))
        self.assertEqual("DIRECT", self.target("DOMAIN-SUFFIX,steamcontent.com"))
        self.assertEqual("DIRECT", self.target("DOMAIN-SUFFIX,store.steampowered.com"))
        self.assertEqual("🧭 节点选择", self.target("DOMAIN-SUFFIX,steamcommunity.com"))
        self.assertEqual([{"name": "land-jp", "dialer-proxy": "🇯🇵 日本自动"}], self.document["proxies"])

    def test_matching_excludes_landing_premium_and_information(self):
        groups = {group["name"]: group for group in self.document["proxy-groups"]}
        relay = re.compile(groups["🧭 节点选择"]["filter"], re.IGNORECASE)
        japan = re.compile(groups["🇯🇵 日本自动"]["filter"], re.IGNORECASE)
        for name in ["JP 01", "Tokyo 02", "日本 03"]:
            self.assertTrue(relay.search(name), name)
            self.assertTrue(japan.search(name), name)
        for name in ["land-jp", "LAND-JP", "JP Premium", "JP [Premium]", "剩余流量 JP", "Expire Date JP", "1 GB | 20 GB"]:
            self.assertFalse(relay.search(name), name)
            self.assertFalse(japan.search(name), name)
        self.assertFalse(japan.search("HK 01"))

    def test_ai_policy_targets_landing_node_without_duplicate_group(self):
        documents = [self.document, yaml.safe_load(
            (ROOT / "dist/latch/latch-naixi-stable.yaml").read_text()
        )]
        for document in documents:
            self.assertNotIn("🤖 AI", [group["name"] for group in document["proxy-groups"]])
            self.assertNotIn("♾️ 中转", [group["name"] for group in document["proxy-groups"]])
            policies = [policy for policy in document["policy-groups"] if policy["name"] == "🤖 AI"]
            self.assertEqual(1, len(policies))
            self.assertEqual("land-jp", policies[0]["target"])
            self.assertEqual(["ai_domain"], policies[0]["rule-sets"])
            source_rules = yaml.safe_load((ROOT / "src/clash/40-rules.yaml").read_text())["rules"]
            expected_conditions = [','.join(rule.split(',')[:2]) for rule in source_rules
                                   if rule.split(',')[0] != "RULE-SET" and rule.split(',')[-1] == "🤖 AI"]
            self.assertEqual(expected_conditions, policies[0]["conditions"])
            self.assertEqual([{"name": "land-jp", "dialer-proxy": "🇯🇵 日本自动"}], document["proxies"])

    def test_excluded_node_groups_reject_invalid_overrides_and_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            profile = root / "src/latch/profile.json"
            original = json.loads(profile.read_text())
            cases = [
                ({"excludeNodeGroups": ["unknown-group"]}, "Unknown source group"),
                ({"nodeGroups": {"♾️ 中转": {"type": "select", "filter": ".*"}}},
                 "Excluded node groups cannot have overrides"),
                ({"chains": {"land-jp": "♾️ 中转"}}, "Invalid chain reference"),
            ]
            for changes, error in cases:
                with self.subTest(changes=changes):
                    settings = {**original, **changes}
                    profile.write_text(json.dumps(settings))
                    with self.assertRaisesRegex(ValueError, error):
                        self.build.latch_document(root)

    def test_providers_and_rule_options_preserve_source(self):
        source = yaml.safe_load((ROOT / "src/clash/30-rule-providers.yaml").read_text())["rule-providers"]
        providers = {k:v for k,v in self.document["rule-providers"].items() if v['type'] != 'inline'}
        self.assertEqual(set(source), set(providers))
        for name, provider in providers.items():
            self.assertEqual("yaml", provider["format"])
            self.assertEqual(source[name]["behavior"], provider["behavior"])
            self.assertEqual(source[name]["interval"], provider["interval"])
            self.assertNotIn("proxy", provider)
            self.assertFalse(provider["path"].endswith(".mrs"))
        self.assertTrue(providers["apple"]["url"].endswith("/Apple_Classical.yaml"))
        source_rules = yaml.safe_load((ROOT / "src/clash/40-rules.yaml").read_text())["rules"]
        import itertools
        runs = [(name, list(lines)) for name, lines in itertools.groupby(source_rules[:-1], lambda line: line.split(',')[2])]
        self.assertEqual(len(runs), len(self.document['policy-groups']))
        for (name, lines), policy in zip(runs, self.document['policy-groups']):
            self.assertEqual({'DIRECT':'直连','REJECT':'拦截'}.get(name,name), policy['name'])
            actual = list(policy.get('conditions', []))
            for ref in policy['rule-sets']:
                provider = self.document['rule-providers'][ref]
                if provider['type'] == 'inline':
                    actual.extend(provider['payload'])
                else:
                    original = next(line for line in lines if line.startswith('RULE-SET,'+ref+','))
                    fields = original.split(',')
                    actual.append(','.join(fields[:2]+fields[3:]))
                    if provider['behavior'] != 'domain':
                        self.assertEqual(','.join(fields[3:]), policy.get('options',''))
            expected = [','.join(line.split(',')[:2]+line.split(',')[3:]) for line in lines]
            self.assertCountEqual(expected, actual)

    def test_named_policies_contain_multiple_rule_sets(self):
        policies = {x['name']: x for x in self.document['policy-groups']}
        self.assertEqual(['telegram_domain','telegram_ip'], policies['✈️ Telegram']['rule-sets'])
        self.assertEqual(['ai_domain'], policies['🤖 AI']['rule-sets'])
        self.assertEqual(20, len(policies['💰 Crypto']['conditions']))
        self.assertEqual(27, len(self.document['policy-groups'])+1)
        self.assertNotIn('rules', self.document)
        self.assertEqual(27, len(self.document['rule-providers']))
        self.assertFalse(any(p['type'] == 'inline' for p in self.document['rule-providers'].values()))
        self.assertNotEqual(policies['📦 Steam 下载CDN']['name'], policies['🛒 Steam 商店支付']['name'])

    def test_local_conditions_do_not_mutate_rule_provider_collection(self):
        providers = {'remote': {'type': 'http', 'behavior': 'domain'}}
        source = ['DOMAIN,first.test,A', 'RULE-SET,remote,A',
                  'IP-CIDR,10.0.0.0/8,A,no-resolve', 'DOMAIN,last.test,B', 'MATCH,DIRECT']
        resolved = [line.replace(',A', ',DIRECT').replace(',B', ',REJECT') for line in source]
        policies = self.build.latch_policy_groups(source, resolved, providers)
        self.assertEqual({'remote': {'type': 'http', 'behavior': 'domain'}}, providers)
        self.assertEqual(['remote'], policies[0]['rule-sets'])
        self.assertEqual(['DOMAIN,first.test', 'IP-CIDR,10.0.0.0/8,no-resolve'], policies[0]['conditions'])
        self.assertEqual([], policies[1]['rule-sets'])
        self.assertEqual(['DOMAIN,last.test'], policies[1]['conditions'])
        self.assertEqual(['DIRECT', 'REJECT'], [p['target'] for p in policies])

    def test_disjoint_policy_runs_keep_priority_and_mixed_resolution_is_rejected(self):
        source = ['DOMAIN,a.test,A','DOMAIN,b.test,B','DOMAIN,c.test,A','MATCH,DIRECT']
        resolved = [line.replace(',A',',DIRECT').replace(',B',',DIRECT') for line in source]
        grouped = self.build.latch_policy_groups(source, resolved, {})
        self.assertEqual(['A','B','A (2)'], [p['name'] for p in grouped])
        mixed = ['RULE-SET,a,A,no-resolve','RULE-SET,b,A','MATCH,DIRECT']
        with self.assertRaisesRegex(ValueError,'Mixed IP resolution'):
            self.build.latch_policy_groups(mixed, mixed, {'a':{'behavior':'ipcidr'},'b':{'behavior':'ipcidr'}})

    def test_policy_override_and_invalid_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "src", root / "src")
            profile = root / "src/latch/profile.json"
            settings = json.loads(profile.read_text())
            settings["policyTargets"]["✈️ Telegram"] = "🇯🇵 日本自动"
            profile.write_text(json.dumps(settings))
            result = self.build.latch_document(root)
            self.assertEqual('🇯🇵 日本自动', next(p['target'] for p in result['policy-groups'] if p['name']=='✈️ Telegram'))
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
