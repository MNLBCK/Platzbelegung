from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_license_is_consistent_between_manifests():
    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    package_json = json.loads((ROOT_DIR / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT_DIR / "package-lock.json").read_text(encoding="utf-8"))

    expected_license = pyproject["project"]["license"]["text"]
    assert package_json["license"] == expected_license
    assert package_lock["packages"][""]["license"] == expected_license


def test_version_source_is_consistent_with_version_file():
    version_tag = (ROOT_DIR / "VERSION").read_text(encoding="utf-8").strip()
    plain_version = version_tag[1:] if version_tag.startswith("v") else version_tag

    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    package_json = json.loads((ROOT_DIR / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT_DIR / "package-lock.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == plain_version
    assert package_json["version"] == plain_version
    assert package_lock["version"] == plain_version
    assert package_lock["packages"][""]["version"] == plain_version
