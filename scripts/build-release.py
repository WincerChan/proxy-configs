from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VERSION = "stable"

CLASH_PARTS = [
    "00-base.yaml",
    "10-proxy-providers.yaml",
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
    "45-filter-apple-push.conf",
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

    return out_path


def build_all(version: str = DEFAULT_VERSION, root: Path = ROOT) -> list[Path]:
    return [
        build_clash(version=version, root=root),
        build_quanx(version=version, root=root),
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
