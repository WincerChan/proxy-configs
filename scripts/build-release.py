from argparse import ArgumentParser
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VERSION = "stable"

CLASH_PARTS = [
    "00-base.yaml",
    "10-proxies.yaml",
    "20-proxy-groups.yaml",
    "30-rule-providers.yaml",
    "40-rules.yaml",
]

QUANX_PARTS = [
    "00-general.conf",
    "10-dns.conf",
    "20-policy.conf",
    "30-server-remote.conf",
    "40-server-local.conf",
    "50-filter-remote.conf",
    "60-rewrite-remote.conf",
    "70-filter-local.conf",
    "80-rewrite-local.conf",
    "90-task-local.conf",
    "91-http-backend.conf",
    "92-mitm.conf",
]


def read_parts(src_dir: Path, parts: list[str], separator: str) -> str:
    chunks = []
    for filename in parts:
        path = src_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing source part: {path}")
        content = path.read_text(encoding="utf-8").rstrip("\n")
        if not content:
            raise ValueError(f"Source part is empty: {path}")
        chunks.append(content)

    return separator.join(chunks) + "\n"


def build_clash(version: str = DEFAULT_VERSION, root: Path = ROOT) -> Path:
    src_dir = root / "src" / "clash"
    out_dir = root / "dist" / "clash"
    out_dir.mkdir(parents=True, exist_ok=True)

    output = read_parts(src_dir, CLASH_PARTS, "\n")
    out_path = out_dir / f"clash-naixi-{version}.yaml"
    out_path.write_text(output, encoding="utf-8")

    return out_path


def build_quanx(version: str = DEFAULT_VERSION, root: Path = ROOT) -> Path:
    src_dir = root / "src" / "quanx"
    out_dir = root / "dist" / "quanx"
    out_dir.mkdir(parents=True, exist_ok=True)

    output = read_parts(src_dir, QUANX_PARTS, "\n\n")
    out_path = out_dir / f"quantumultx-naixi-{version}.conf"
    out_path.write_text(output, encoding="utf-8")

    push_src = root / "rules" / "apple-push.list"
    if push_src.exists():
        (out_dir / "apple-push.list").write_text(
            push_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    return out_path


def latch_policy_groups(source_rules: list[str], resolved_rules: list[str], providers: dict) -> list[dict]:
    """Keep adjacent source policies and their first-match priority intact."""
    result = []
    names = set()
    local_payload = []
    remote_options = set()

    def finish():
        if not result:
            return
        policy = result[-1]
        if len(remote_options) > 1:
            raise ValueError(f"Mixed IP resolution semantics in policy: {policy['name']}")
        if remote_options == {"no-resolve"}:
            if any(line.split(',')[0] in {'IP-CIDR', 'IP-CIDR6', 'GEOIP'} and not line.endswith(',no-resolve') for line in local_payload):
                raise ValueError(f"Mixed IP resolution semantics in policy: {policy['name']}")
            policy['options'] = 'no-resolve'
        if local_payload:
            policy['conditions'] = list(local_payload)

    previous = None
    for original, resolved in zip(source_rules, resolved_rules):
        source_fields = [part.strip() for part in original.split(',')]
        fields = resolved.split(',')
        if fields[0] == 'MATCH':
            finish()
            break
        source_target = source_fields[2]
        if source_target != previous:
            finish()
            local_payload = []
            remote_options = set()
            base = {'DIRECT': '直连', 'REJECT': '拦截'}.get(source_target, source_target)
            name = base
            suffix = 2
            while name in names:
                name = f'{base} ({suffix})'
                suffix += 1
            names.add(name)
            result.append({'name': name, 'target': fields[2], 'rule-sets': []})
            previous = source_target
        options = ','.join(fields[3:])
        if options not in {'', 'no-resolve'}:
            raise ValueError(f"Unsupported policy rule options: {resolved}")
        if fields[0] == 'RULE-SET':
            ref = fields[1]
            if ref not in result[-1]['rule-sets']:
                result[-1]['rule-sets'].append(ref)
            if providers[ref]['behavior'] != 'domain':
                remote_options.add(options)
        else:
            local_payload.append(','.join(fields[:2] + fields[3:]))
    return result


def latch_document(root: Path = ROOT) -> dict:
    """Adapt routing to Latch's node-only groups without importing credentials."""
    source = yaml.safe_load(read_parts(root / "src" / "clash", CLASH_PARTS, "\n"))
    settings = json.loads((root / "src" / "latch" / "profile.json").read_text(encoding="utf-8"))
    groups = {group["name"]: group for group in source["proxy-groups"]}
    if len(groups) != len(source["proxy-groups"]):
        raise ValueError("Duplicate source group name")
    fixed = settings.get("nodeGroups", {})
    policies = settings.get("policyTargets", {})
    overrides = settings.get("providerOverrides", {})
    chains = settings.get("chains", {})
    for name in set(fixed) | set(policies):
        if name not in groups:
            raise ValueError(f"Unknown source group: {name}")
    for name, target in policies.items():
        if name in fixed or target not in groups[name].get("proxies", []):
            raise ValueError(f"Invalid policy choice for {name}: {target}")

    native = {}
    for name, group in groups.items():
        if name in fixed:
            native[name] = {"name": name, **fixed[name]}
        elif group.get("include-all-proxies"):
            pattern = group.get("filter", ".*").replace("(?i)", "")
            exclude = group.get("exclude-filter", "").replace("(?i)", "")
            if exclude:
                pattern = f"^(?!.*(?:{exclude}))(?=.*(?:{pattern})).*$"
            native[name] = {"name": name, "type": group["type"], "filter": pattern}
    for name, group in native.items():
        if group.get("type") not in {"select", "url-test", "fallback", "load-balance"} or not group.get("filter"):
            raise ValueError(f"Invalid Latch node group: {name}")

    node_names = {node["name"] for node in source.get("proxies", [])} | set(chains)

    def resolve(name: str, seen: tuple = ()) -> str:
        if name in native or name in {"DIRECT", "REJECT"} or name in node_names:
            return name
        if name in seen:
            raise ValueError(f"Policy cycle: {' -> '.join((*seen, name))}")
        if name not in groups or not groups[name].get("proxies"):
            raise ValueError(f"Unresolved policy: {name}")
        return resolve(policies.get(name, groups[name]["proxies"][0]), (*seen, name))

    rules = []
    used = set()
    for raw in source["rules"]:
        fields = [field.strip() for field in raw.split(",")]
        index = 1 if fields[0] == "MATCH" else 2
        if len(fields) <= index:
            raise ValueError(f"Invalid source rule: {raw}")
        fields[index] = resolve(fields[index])
        if fields[0] == "RULE-SET":
            used.add(fields[1])
        rules.append(",".join(fields))
    if sum(rule.startswith("MATCH,") for rule in rules) != 1 or not rules[-1].startswith("MATCH,"):
        raise ValueError("Expected one final MATCH rule")
    if set(overrides) - set(source["rule-providers"]):
        raise ValueError("Provider override names must exist in source")
    providers = {}
    for name, original in source["rule-providers"].items():
        if name not in used:
            continue
        provider = deepcopy(original)
        provider.update(overrides.get(name, {}))
        if provider.get("format") == "mrs":
            url = urlsplit(provider["url"])
            if url.hostname != "raw.githubusercontent.com" or not url.path.startswith("/MetaCubeX/meta-rules-dat/meta/geo/") or not url.path.endswith(".mrs") or url.query or url.fragment:
                raise ValueError(f"No verified YAML equivalent for {name}")
            provider["url"] = provider["url"][:-4] + ".yaml"
            provider["format"] = "yaml"
            if "path" in provider:
                provider["path"] = str(Path(provider["path"]).with_suffix(".yaml"))
        if provider.get("type") not in {"http", "file"} or provider.get("format", "yaml") not in {"yaml", "text"}:
            raise ValueError(f"Unsupported Latch provider: {name}")
        if provider.get("behavior") not in {"domain", "ipcidr", "classical"}:
            raise ValueError(f"Unsupported provider behavior: {name}")
        # The Latch provider contract has no per-download proxy selector.
        allowed = {"type", "behavior", "format", "interval", "path", "url"}
        providers[name] = {key: value for key, value in provider.items() if key in allowed}
    if used - set(providers):
        raise ValueError("Rules reference missing providers")

    references = []
    for name, via in chains.items():
        if name in native or via not in native and via not in node_names:
            raise ValueError(f"Invalid chain reference: {name} -> {via}")
        seen = {name}
        cursor = via
        while cursor in chains:
            if cursor in seen:
                raise ValueError(f"Chain cycle at {cursor}")
            seen.add(cursor)
            cursor = chains[cursor]
        if cursor in seen:
            raise ValueError(f"Chain cycle at {cursor}")
        references.append({"name": name, "dialer-proxy": via})
    policy_groups = latch_policy_groups(source['rules'], rules, providers)
    return {"proxies": references, "proxy-groups": list(native.values()), "rule-providers": providers,
            "policy-groups": policy_groups, "fallback": rules[-1].split(',')[1]}


def build_latch(version: str = DEFAULT_VERSION, root: Path = ROOT) -> Path:
    document = latch_document(root)
    output = (
        "# Latch routing import; not a standalone latch-kernel startup config.\n"
        "# Import real nodes first; land-jp must use Trojan or AnyTLS.\n"
        "# Requires policy-groups and conditions import support; see docs/latch.md.\n"
        + yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    )
    out_path = root / "dist" / "latch" / f"latch-naixi-{version}.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    return out_path


def build_all(version: str = DEFAULT_VERSION, root: Path = ROOT) -> list[Path]:
    return [
        build_clash(version=version, root=root),
        build_quanx(version=version, root=root),
        build_latch(version=version, root=root),
    ]


def parse_args() -> str:
    parser = ArgumentParser(description="Build release configs from src parts.")
    parser.add_argument(
        "version",
        nargs="?",
        default=DEFAULT_VERSION,
        help="release version suffix, for example stable or v1.0.0",
    )
    return parser.parse_args().version


def main() -> None:
    for out_path in build_all(version=parse_args()):
        print(f"Built: {out_path}")

if __name__ == "__main__":
    main()
