from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STEAM_POLICIES = {
    "🎮 Steam 登录社区",
    "🛒 Steam 商店支付",
    "📦 Steam 下载CDN",
}


def load_clash_group_names(path: Path) -> set[str]:
    groups = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- name:"):
            groups.add(line.removeprefix("- name:").strip())
    return groups


def load_clash_rules(path: Path) -> list[tuple[str, str, str]]:
    rules = []
    in_rules = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "rules:":
            in_rules = True
            continue
        if not in_rules or not line.startswith("- "):
            continue

        parts = [part.strip() for part in line.removeprefix("- ").split(",")]
        if len(parts) >= 3:
            rules.append((parts[0], parts[1], parts[2]))
    return rules


def load_quanx_policies(path: Path) -> set[str]:
    policies = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("static = "):
            continue
        policies.add(line.removeprefix("static = ").split(",", 1)[0].strip())
    return policies


def load_quanx_filter_policies(path: Path) -> dict[tuple[str, str], str]:
    filters = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("["):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            filters[(parts[0], parts[1])] = parts[2]
    return filters


class SteamSplitTests(unittest.TestCase):
    def test_clash_has_split_steam_groups_without_legacy_group(self):
        groups = load_clash_group_names(
            ROOT / "dist" / "clash" / "clash-naixi-stable.yaml"
        )

        self.assertNotIn("🎮 Steam", groups)
        for policy in STEAM_POLICIES:
            self.assertIn(policy, groups)

    def test_clash_routes_steam_domains_to_specific_policies(self):
        rules = load_clash_rules(ROOT / "dist" / "clash" / "clash-naixi-stable.yaml")
        by_match = {(kind, value): policy for kind, value, policy in rules}

        self.assertNotIn(("RULE-SET", "steam_domain"), by_match)
        self.assertEqual(
            "📦 Steam 下载CDN",
            by_match[("DOMAIN-SUFFIX", "steamcontent.com")],
        )
        self.assertEqual(
            "🛒 Steam 商店支付",
            by_match[("DOMAIN-SUFFIX", "steampowered.com")],
        )
        self.assertEqual(
            "🎮 Steam 登录社区",
            by_match[("DOMAIN-SUFFIX", "steamcommunity.com")],
        )

    def test_quanx_has_split_steam_policies_without_legacy_policy(self):
        policies = load_quanx_policies(
            ROOT / "dist" / "quanx" / "quantumultx-naixi-stable.conf"
        )

        self.assertNotIn("🎮 Steam", policies)
        for policy in STEAM_POLICIES:
            self.assertIn(policy, policies)

    def test_quanx_routes_steam_domains_to_specific_policies(self):
        filters = load_quanx_filter_policies(
            ROOT / "dist" / "quanx" / "quantumultx-naixi-stable.conf"
        )

        self.assertEqual(
            "📦 Steam 下载CDN",
            filters[("host-suffix", "steamcontent.com")],
        )
        self.assertEqual(
            "🛒 Steam 商店支付",
            filters[("host-suffix", "steampowered.com")],
        )
        self.assertEqual(
            "🎮 Steam 登录社区",
            filters[("host-suffix", "steamcommunity.com")],
        )

    def test_quanx_does_not_import_mixed_game_download_rules(self):
        config = (
            ROOT / "dist" / "quanx" / "quantumultx-naixi-stable.conf"
        ).read_text(encoding="utf-8")

        self.assertNotIn("GameDownload.list", config)
        self.assertIn("host, download.epicgames.com, 🎮 Games", config)


if __name__ == "__main__":
    unittest.main()
