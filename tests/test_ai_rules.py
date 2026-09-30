from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AiRulesTests(unittest.TestCase):
    def test_ai_category_precedes_general_service_rules(self):
        providers = (ROOT / "src/clash/30-rule-providers.yaml").read_text()
        self.assertIn("/geosite/category-ai-!cn.mrs", providers)
        self.assertIn("  ai_domain:", providers)
        rules = (ROOT / "src/clash/40-rules.yaml").read_text()
        for provider in ["google_domain", "microsoft_domain", "github_domain"]:
            self.assertLess(rules.index("RULE-SET,ai_domain,"),
                            rules.index("RULE-SET," + provider + ","))
        remote = (ROOT / "src/quanx/50-filter-remote.conf").read_text()
        ai = next(line for line in remote.splitlines() if "force-policy=🤖 AI" in line)
        self.assertIn("category-ai-!cn.list", ai)
        self.assertIn("opt-parser=true", ai)
        self.assertIn("update-interval=86400", ai)
        for tag in ["Google", "Microsoft", "GitHub", "Global"]:
            self.assertLess(remote.index(ai), remote.index("tag=" + tag + ","))

    def test_claude_fallbacks_and_no_broad_ai_keywords(self):
        clash = (ROOT / "src/clash/40-rules.yaml").read_text()
        qx = (ROOT / "src/quanx/70-filter-local.conf").read_text()
        for domain in ["anthropic.com", "clau.de", "claude.ai", "claude.com",
                       "claudeusercontent.com", "claudemcpclient.com", "claudemcpcontent.com"]:
            self.assertIn(f"DOMAIN-SUFFIX,{domain},🤖 AI", clash)
            self.assertIn(f"host-suffix, {domain}, 🤖 AI, via-interface=%TUN%", qx)
        self.assertFalse(any("DOMAIN-KEYWORD" in line and "🤖 AI" in line
                             for line in clash.splitlines()))
        self.assertFalse(any("host-keyword" in line and "🤖 AI" in line
                             for line in qx.splitlines()))
