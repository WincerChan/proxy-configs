from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_PATH = Path("dist/clash/clash-naixi-stable.yaml")
REQUIRED_KEYS = ["proxy-providers", "proxy-groups", "rules"]


def scan_required_structure(path: Path) -> tuple[set[str], set[str]]:
    keys = set()
    group_names = set()
    in_proxy_groups = False

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue

        if not line.startswith((" ", "-")) and ":" in line:
            key = line.split(":", 1)[0]
            keys.add(key)
            in_proxy_groups = key == "proxy-groups"
            continue

        if in_proxy_groups and line.startswith("- name:"):
            group_names.add(line.split(":", 1)[1].strip().strip("'\""))

    return keys, group_names


def validate_with_yaml(path: Path) -> tuple[set[str], set[str]]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at document root: {path}")

    group_names = {
        group["name"]
        for group in data.get("proxy-groups", [])
        if isinstance(group, dict) and "name" in group
    }
    return set(data), group_names


def validate(path: Path) -> int:
    keys, group_names = (
        validate_with_yaml(path) if yaml is not None else scan_required_structure(path)
    )

    for key in REQUIRED_KEYS:
        if key not in keys:
            raise ValueError(f"Missing required key: {key}")

    if not group_names:
        raise ValueError("Missing proxy group names")

    return len(group_names)


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
