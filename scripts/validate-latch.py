"""Validate the import artifact, optionally through real Latch executables."""
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import urlopen

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "dist/latch/latch-naixi-stable.yaml"
MAX_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 262144


def validate(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = {group["name"]: group for group in document["proxy-groups"]}
    nodes = {node["name"] for node in document["proxies"]}
    if len(groups) != len(document["proxy-groups"]):
        raise ValueError("Duplicate group name")
    for group in groups.values():
        if set(group) != {"name", "type", "filter"}:
            raise ValueError("Latch import groups must be node matchers")
        re.compile(group["filter"], re.IGNORECASE)
    providers = document["rule-providers"]
    policies = document.get('policy-groups')
    if not isinstance(policies,list) or not policies or 'rules' in document:
        raise ValueError('Expected named policy-groups, not flattened rules')
    names = set()
    for policy in policies:
        target = policy['target']
        if target not in groups and target not in nodes and target not in {"DIRECT", "REJECT"}:
            raise ValueError(f"Unresolved rule target: {target}")
        if not policy['name'] or policy['name'] in names or not (policy['rule-sets'] or policy.get('conditions')) or len(set(policy['rule-sets'])) != len(policy['rule-sets']):
            raise ValueError('Policy names and set references must be nonempty and unique')
        conditions = policy.get('conditions', [])
        if not isinstance(conditions, list) or any(not isinstance(x, str) or len(x.split(',')) not in {2, 3} for x in conditions):
            raise ValueError('Invalid policy conditions')
        names.add(policy['name'])
        if set(policy['rule-sets']) - set(providers):
            raise ValueError('Policy references unknown rule sets')
        if set(policy) - {'name','target','rule-sets','conditions','options'} or policy.get('options','') not in {'','no-resolve'}:
            raise ValueError('Unsupported policy fields or options')
    if document.get('fallback') not in groups and document.get('fallback') not in nodes and document.get('fallback') not in {'DIRECT','REJECT'}:
        raise ValueError('Expected a known fallback target')
    for provider in providers.values():
        if provider.get('type') == 'inline':
            if set(provider) != {'type','behavior','payload','interval'} or provider['behavior'] != 'classical' or not provider['payload'] or not all(isinstance(x,str) for x in provider['payload']):
                raise ValueError('Invalid local rule set')
            continue
        if provider.get("format") != "yaml" or set(provider) - {"type", "behavior", "format", "interval", "path", "url"}:
            raise ValueError("Unsupported Latch provider contract")
    for node in document["proxies"]:
        if set(node) != {"name", "dialer-proxy"} or node["dialer-proxy"] not in groups | dict.fromkeys(nodes):
            raise ValueError("Chain reference must not contain credentials or an unknown relay")
    return document


def fetch_providers(document: dict) -> dict:
    def fetch(item):
        name, provider = item
        with urlopen(provider["url"], timeout=20) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError(f"Provider exceeds download limit: {name}")
        payload = yaml.safe_load(data).get("payload", [])
        if not 1 <= len(payload) <= MAX_ENTRIES or not all(isinstance(item, str) for item in payload):
            raise ValueError(f"Invalid or oversized payload: {name}")
        return name, data, len(payload)

    with ThreadPoolExecutor(max_workers=6) as pool:
        remote = [(name,p) for name,p in document['rule-providers'].items() if p['type']=='http']
        return {name: (data, count) for name, data, count in pool.map(fetch, remote)}


def verify_business(path: Path, business: str | None, kernel: str | None, downloaded: dict, dll_path: str | None = None) -> dict:
    library = ctypes.CDLL(dll_path) if dll_path else None
    if library:
        if library.LatchBusinessABIVersion() != 1:
            raise ValueError("Unsupported Latch business ABI")
        library.LatchBusinessCall.argtypes = [ctypes.c_char_p]
        library.LatchBusinessCall.restype = ctypes.c_void_p
        library.LatchBusinessFree.argtypes = [ctypes.c_void_p]
        library.LatchBusinessFree.restype = None

    def call(method, params):
        request = json.dumps({"version": 1, "method": method, "params": params})
        if library:
            pointer = library.LatchBusinessCall(request.encode("utf-8"))
            if not pointer:
                raise ValueError("Latch business ABI returned a null response")
            try:
                response = json.loads(ctypes.string_at(pointer).decode("utf-8"))
            finally:
                library.LatchBusinessFree(pointer)
        else:
            result = subprocess.run([business], input=request + "\n", capture_output=True, text=True, check=True)
            response = json.loads(result.stdout)
        if response.get("error"):
            raise ValueError(response["error"]["message"])
        return response["result"]

    # Controlled fixtures only: no real credentials, client data or traffic.
    node_names = {"jp": "JP 01", "hk": "HK 01", "sg": "SG 01", "premium": "JP Premium", "traffic": "剩余流量 JP", "land": "land-jp"}
    nodes = [{"id": key, "name": name, "source": "fixture", "region": "--", "config": {"type": "trojan", "server": "fixture.invalid", "port": 443, "password": "fixture-password"}} for key, name in node_names.items()]
    config = {
        "schema": 1, "nodes": nodes, "groups": [], "activeProfile": "initial",
        "profiles": [{"id": "initial", "name": "Initial", "rules": [{"id": "fallback", "name": "Fallback", "type": "MATCH", "values": [], "target": "DIRECT", "enabled": True}], "chains": {}, "providers": {}}],
        "settings": {"mode": "rule", "port": 7890, "allowLan": False, "ipv6": False, "logLevel": "info", "tun": False, "stack": "mixed", "dnsMode": "redir-host", "dns": ["1.1.1.1"], "testUrl": "https://www.gstatic.com/generate_204", "defaultExit": "DIRECT"},
    }
    document = call("import.parse", {"text": path.read_text(encoding="utf-8")})
    source = validate(path)
    policies = call('config.importPolicies', {'document':document, 'config':config, 'mode':'replace'})
    current = next(p for p in policies['profiles'] if p['id']==policies['activeProfile'])
    if len(current['rules']) != len(source['policy-groups'])+1:
        raise ValueError('Policy import flattened grouped rules')
    for actual, expected in zip(current['rules'], source['policy-groups']):
        if actual['name'] != expected['name'] or actual['values'] != expected['rule-sets'] or actual['options'] != expected.get('options','') or actual.get('conditions',[]) != expected.get('conditions',[]):
            raise ValueError('Policy name, set nesting or options changed during import')
    imported = call("import.profile", {"document": document, "config": config, "name": "Latch fixture"})
    config, profile = imported["config"], imported["profile"]
    config["profiles"].append(profile)
    config["activeProfile"] = profile["id"]
    groups = {group["name"]: group for group in config["groups"]}
    if "🤖 AI" in groups:
        raise ValueError("AI must be a policy targeting the landing node, not a node group")
    if "♾️ 中转" in groups:
        raise ValueError("Latch must reuse an existing node group for the relay")
    ai_policy = next(rule for rule in profile["rules"] if rule["name"] == "🤖 AI")
    if ai_policy["target"] != "land":
        raise ValueError("AI policy did not resolve directly to the landing node")
    for name, expected in {"🧭 节点选择": {"jp", "hk", "sg"}, "🇯🇵 日本自动": {"jp"}}.items():
        members = call("group.members", {"group": groups[name], "nodes": nodes})
        if set(members) != expected:
            raise ValueError(f"Real Latch group matcher differs: {name}")
    relay_id = groups["🇯🇵 日本自动"]["id"]
    if profile["chains"] != {"land": relay_id}:
        raise ValueError("Landing/relay chain was not preserved")
    if call("chain.path", {"config": config, "exit": "land"}) != [relay_id, "land"]:
        raise ValueError("Wrong chain direction")
    compiled = call("config.compile", {"config": config, "controllerPort": 19090, "secret": "fixture-secret"})
    landing = next(proxy for proxy in compiled["proxies"] if proxy["name"] == "land")
    if landing.get("dialer-proxy") != relay_id:
        raise ValueError("Compiled chain was not preserved")

    ai_source = next(policy for policy in source["policy-groups"] if policy["name"] == "🤖 AI")
    ai_matches = [("RULE-SET", ref) for ref in ai_source["rule-sets"]]
    ai_matches.extend(tuple(condition.split(",")[:2]) for condition in ai_source.get("conditions", []))

    def verify_ai_exit(document, expected):
        for match in ai_matches:
            targets = [rule.split(",")[2] for rule in document["rules"]
                       if tuple(rule.split(",")[:2]) == match]
            if targets != [expected]:
                raise ValueError(f"Unexpected compiled AI exit for {match}: {targets}")

    verify_ai_exit(compiled, "land")

    # An absent landing node must still REJECT all AI routing.
    absent = json.loads(json.dumps(config))
    absent["nodes"] = [node for node in absent["nodes"] if node["id"] != "land"]
    blocked = call("config.compile", {"config": absent, "controllerPort": 19090, "secret": "fixture-secret"})
    verify_ai_exit(blocked, "REJECT")

    if kernel:
        if not downloaded:
            raise ValueError("Kernel validation requires --online to load real lists")
        with tempfile.TemporaryDirectory(prefix="latch-profile-verify-") as directory:
            temp = Path(directory)
            for name, (data, _) in downloaded.items():
                source = temp / f"{name}.yaml"
                source.write_bytes(data)
                compiled["rule-providers"][name] = {"type": "file", "behavior": compiled["rule-providers"][name]["behavior"], "format": "yaml", "path": str(source), "interval": 0}
            config_path = temp / "compiled.json"
            config_path.write_text(json.dumps(compiled), encoding="utf-8")
            subprocess.run([kernel, "check", "-c", str(config_path), "-d", str(temp)], capture_output=True, text=True, check=True)
    return {"businessImportCompile": True, "groupedPolicyImport":True, "groupMatching": True, "chainDirection": True, "missingLandingRejected": True, "kernelLoadsRealProviders": bool(kernel)}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--online", action="store_true")
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument("--business", help="Path to real latch-business CLI")
    backend.add_argument("--business-dll", help="Path to Windows latch-core.dll; uses pure business ABI")
    parser.add_argument("--kernel", help="Path to real latch-kernel CLI")
    args = parser.parse_args()
    if args.kernel and not (args.business or args.business_dll):
        parser.error("--kernel requires --business or --business-dll")
    document = validate(args.path)
    downloaded = fetch_providers(document) if args.online else {}
    report = {"groups": len(document["proxy-groups"]), "providers": len(document["rule-providers"]), "policyGroups": len(document["policy-groups"])+1, "onlineProviders": {name: {"bytes": len(data), "entries": count} for name, (data, count) in downloaded.items()}}
    if args.business or args.business_dll:
        report.update(verify_business(args.path, args.business, args.kernel, downloaded, args.business_dll))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
