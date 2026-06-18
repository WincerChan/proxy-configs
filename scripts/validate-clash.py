from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_PATH = Path("dist/clash/clash-naixi-stable.yaml")
REQUIRED_KEYS = ["proxy-providers", "proxy-groups", "rules"]
REQUIRED_BUSINESS_PROXIES = [
    "🇭🇰 香港自动",
    "🇹🇼 台湾自动",
    "🇺🇸 美国自动",
    "🇯🇵 日本自动",
    "🇸🇬 新加坡自动",
    "♻️ 自动低延迟",
    "🛟 故障切换",
    "🚀 代理",
]
NON_BUSINESS_GROUPS = {
    "🚀 代理",
    "🧭 节点选择",
    "📊 流量看板",
    "♻️ 自动低延迟",
    "🛟 故障切换",
    "🇭🇰 香港自动",
    "🇹🇼 台湾自动",
    "🇯🇵 日本自动",
    "🇸🇬 新加坡自动",
    "🇺🇸 美国自动",
    "🇰🇷 韩国自动",
    "🇬🇧 英国自动",
    "🇪🇺 欧洲自动",
    "🇨🇦 加拿大自动",
    "🇦🇺 澳洲自动",
    "🇨🇳 直连",
    "🐟 Final",
}


def scan_required_structure(path: Path) -> tuple[set[str], dict[str, list[str]]]:
    keys = set()
    groups: dict[str, list[str]] = {}
    in_proxy_groups = False
    in_proxies = False
    current_group = None

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue

        if not line.startswith((" ", "-")) and ":" in line:
            key = line.split(":", 1)[0]
            keys.add(key)
            in_proxy_groups = key == "proxy-groups"
            in_proxies = False
            current_group = None
            continue

        if in_proxy_groups and line.startswith("- name:"):
            current_group = line.split(":", 1)[1].strip().strip("'\"")
            groups[current_group] = []
            in_proxies = False
            continue

        if in_proxy_groups and current_group and line.strip() == "proxies:":
            in_proxies = True
            continue

        if (
            in_proxy_groups
            and current_group
            and line.startswith("  ")
            and not line.startswith("  - ")
        ):
            in_proxies = False
            continue

        if in_proxy_groups and current_group and in_proxies and line.startswith("  - "):
            groups[current_group].append(line.split("-", 1)[1].strip().strip("'\""))

    return keys, groups


def validate_with_yaml(path: Path) -> tuple[set[str], dict[str, list[str]]]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at document root: {path}")

    groups = {
        group["name"]: group.get("proxies", [])
        for group in data.get("proxy-groups", [])
        if isinstance(group, dict) and "name" in group
    }
    return set(data), groups


def load_structure(path: Path) -> tuple[set[str], dict[str, list[str]]]:
    return validate_with_yaml(path) if yaml is not None else scan_required_structure(path)


def business_groups(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        name: proxies
        for name, proxies in groups.items()
        if name not in NON_BUSINESS_GROUPS and proxies
    }


def validate_business_groups(groups: dict[str, list[str]]) -> None:
    missing_by_group = {
        name: [
            required_proxy
            for required_proxy in REQUIRED_BUSINESS_PROXIES
            if required_proxy not in proxies
        ]
        for name, proxies in business_groups(groups).items()
    }
    missing_by_group = {
        name: missing
        for name, missing in missing_by_group.items()
        if missing
    }
    if missing_by_group:
        details = "; ".join(
            f"{name}: {', '.join(missing)}"
            for name, missing in sorted(missing_by_group.items())
        )
        raise ValueError(f"Business proxy groups missing required proxies: {details}")


def validate(path: Path) -> int:
    keys, groups = load_structure(path)

    for key in REQUIRED_KEYS:
        if key not in keys:
            raise ValueError(f"Missing required key: {key}")

    if not groups:
        raise ValueError("Missing proxy group names")

    validate_business_groups(groups)

    return len(groups)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    group_count = validate(path)
    status = "YAML OK" if yaml is not None else "YAML structure OK"
    print(f"{status}: {path}")
    print(f"Proxy groups: {group_count}")

if __name__ == "__main__":
    main()
