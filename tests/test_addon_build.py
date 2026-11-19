"""The add-on (app) builds from its Dockerfile alone, as Supervisor 2026.04+ does it (issue #2)."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).parents[1]
ADDON = ROOT / "speaker_id"


def test_dockerfile_has_a_fixed_debian_base_image():
    lines = (ADDON / "Dockerfile").read_text(encoding="utf-8").splitlines()
    froms = [line for line in lines if line.startswith("FROM ")]
    assert froms == ["FROM python:3.12-slim-bookworm"]
    assert not any("BUILD_FROM" in line for line in lines if not line.startswith("#"))


def test_no_deprecated_build_file():
    assert not (ADDON / "build.yaml").exists()
    assert not (ADDON / "build.json").exists()


def test_addon_and_integration_versions_match():
    config = (ADDON / "config.yaml").read_text(encoding="utf-8")
    addon = re.search(r'^version: "([^"]+)"', config, re.M)
    manifest_file = ROOT / "custom_components/speaker_id/manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert addon and addon.group(1) == manifest["version"]
