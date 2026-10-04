from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

PLUGIN_NAME = "astrbot_plugin_group_reply_gate"
PACKAGE_ITEMS = (
    "_conf_schema.json",
    "gate",
    "LICENSE",
    "main.py",
    "metadata.yaml",
    "README.md",
)
EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "dist",
    "docs",
    "scripts",
    "tests",
}


def read_version(metadata_path: Path) -> str:
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "version":
            version = value.strip().strip("'\"")
            if version:
                return version
    raise ValueError(f"Missing version in {metadata_path}")


def build_archive(repo_root: Path, output_dir: Path) -> Path:
    version = read_version(repo_root / "metadata.yaml")
    missing = [item for item in PACKAGE_ITEMS if not (repo_root / item).exists()]
    if missing:
        raise FileNotFoundError(f"Missing package items: {', '.join(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{PLUGIN_NAME}-v{version}.zip"
    staging_root = output_dir / f".{PLUGIN_NAME}-staging"
    package_root = staging_root / PLUGIN_NAME

    if staging_root.exists():
        shutil.rmtree(staging_root)
    package_root.mkdir(parents=True)

    try:
        for item in PACKAGE_ITEMS:
            source = repo_root / item
            destination = package_root / item
            if source.is_dir():
                shutil.copytree(
                    source,
                    destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            else:
                shutil.copy2(source, destination)

        if archive_path.exists():
            archive_path.unlink()
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in sorted(package_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging_root))
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    verify_archive(archive_path)
    return archive_path


def verify_archive(archive_path: Path) -> None:
    expected_root = f"{PLUGIN_NAME}/"
    with zipfile.ZipFile(archive_path) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise ValueError(f"Corrupt archive member: {bad_file}")
        names = archive.namelist()

    if not names or any(not name.startswith(expected_root) for name in names):
        raise ValueError("Archive must contain exactly one plugin root directory")
    required = {
        f"{expected_root}_conf_schema.json",
        f"{expected_root}main.py",
        f"{expected_root}metadata.yaml",
    }
    missing = required - set(names)
    if missing:
        raise ValueError(f"Archive is missing required files: {sorted(missing)}")
    for name in names:
        parts = set(Path(name).parts)
        if parts & EXCLUDED_PARTS:
            raise ValueError(f"Archive contains excluded path: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the AstrBot plugin archive")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist"),
        help="Output directory (default: dist)",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    archive = build_archive(repo_root, args.output.resolve())
    print(archive)


if __name__ == "__main__":
    main()
