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
    matches = 0
    for index, raw in enumerate(document["rules"]):
        fields = raw.split(",")
        kind = fields[0]
        target = fields[1] if kind == "MATCH" else fields[2]
        if target not in groups and target not in nodes and target not in {"DIRECT", "REJECT"}:
            raise ValueError(f"Unresolved rule target: {target}")
        if kind == "RULE-SET" and fields[1] not in providers:
            raise ValueError(f"Unknown provider: {fields[1]}")
        if kind == "MATCH":
            matches += 1
            if index != len(document["rules"]) - 1:
                raise ValueError("MATCH must be last")
    if matches != 1:
        raise ValueError("Expected one MATCH")
    for provider in providers.values():
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
        return {name: (data, count) for name, data, count in pool.map(fetch, document["rule-providers"].items())}


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
        "settings": {"kernel": "latch", "mode": "rule", "port": 7890, "allowLan": False, "ipv6": False, "logLevel": "info", "tun": False, "stack": "mixed", "dnsMode": "redir-host", "dns": ["1.1.1.1"], "testUrl": "https://www.gstatic.com/generate_204", "defaultExit": "DIRECT"},
    }
    document = call("import.parse", {"text": path.read_text(encoding="utf-8")})
    imported = call("import.profile", {"document": document, "config": config, "name": "Latch fixture"})
    config, profile = imported["config"], imported["profile"]
    config["profiles"].append(profile)
    config["activeProfile"] = profile["id"]
    groups = {group["name"]: group for group in config["groups"]}
    for name, expected in {"♾️ 中转": {"jp", "hk", "sg"}, "🇯🇵 日本自动": {"jp"}, "🤖 AI": {"land"}}.items():
        members = call("group.members", {"group": groups[name], "nodes": nodes})
        if set(members) != expected:
            raise ValueError(f"Real Latch group matcher differs: {name}")
    if profile["chains"] != {"land": groups["♾️ 中转"]["id"]}:
        raise ValueError("Landing/relay chain was not preserved")
    if call("chain.path", {"config": config, "exit": "land"}) != [groups["♾️ 中转"]["id"], "land"]:
        raise ValueError("Wrong chain direction")
    compiled = call("config.compile", {"config": config, "controllerPort": 19090, "secret": "fixture-secret"})
    landing = next(proxy for proxy in compiled["proxies"] if proxy["name"] == "land")
    if landing.get("dialer-proxy") != groups["♾️ 中转"]["id"]:
        raise ValueError("Compiled chain was not preserved")

    # An absent landing node must leave an empty AI group and REJECT routing.
    absent = json.loads(json.dumps(config))
    absent["nodes"] = [node for node in absent["nodes"] if node["id"] != "land"]
    blocked = call("config.compile", {"config": absent, "controllerPort": 19090, "secret": "fixture-secret"})
    ai = next(group for group in blocked["proxy-groups"] if group["name"] == groups["🤖 AI"]["id"])
    if ai["proxies"] != ["REJECT"]:
        raise ValueError("Missing landing node did not fail closed")

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
    return {"businessImportCompile": True, "groupMatching": True, "chainDirection": True, "missingLandingRejected": True, "kernelLoadsRealProviders": bool(kernel)}


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
    report = {"groups": len(document["proxy-groups"]), "providers": len(document["rule-providers"]), "rules": len(document["rules"]), "onlineProviders": {name: {"bytes": len(data), "entries": count} for name, (data, count) in downloaded.items()}}
    if args.business or args.business_dll:
        report.update(verify_business(args.path, args.business, args.kernel, downloaded, args.business_dll))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
