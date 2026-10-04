from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.build_release import PLUGIN_NAME, build_archive, read_version


def test_metadata_version_is_one_zero_zero() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert read_version(repo_root / "metadata.yaml") == "1.0.0"


def test_release_archive_is_installable_and_excludes_development_files(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    archive_path = build_archive(repo_root, tmp_path)

    assert archive_path.name == f"{PLUGIN_NAME}-v1.0.0.zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    root = f"{PLUGIN_NAME}/"
    assert f"{root}main.py" in names
    assert f"{root}metadata.yaml" in names
    assert f"{root}_conf_schema.json" in names
    assert any(name.startswith(f"{root}gate/") for name in names)
    assert not any("/tests/" in name for name in names)
    assert not any("/.github/" in name for name in names)
    assert not any(name.endswith("/AGENTS.md") for name in names)
