#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_INPUT="${1:-}"

usage() {
  echo "Usage: bash scripts/release.sh v0.1.71" >&2
  exit 1
}

if [[ -z "$VERSION_INPUT" ]]; then
  usage
fi

if [[ "$VERSION_INPUT" =~ ^v[0-9]+(\.[0-9]+)+$ ]]; then
  TAG_VERSION="$VERSION_INPUT"
elif [[ "$VERSION_INPUT" =~ ^[0-9]+(\.[0-9]+)+$ ]]; then
  TAG_VERSION="v$VERSION_INPUT"
else
  echo "Ungültige Versionsnummer: $VERSION_INPUT" >&2
  usage
fi

PLAIN_VERSION="${TAG_VERSION#v}"

require_clean_worktree() {
  if ! git -C "$ROOT_DIR" diff --quiet || ! git -C "$ROOT_DIR" diff --cached --quiet; then
    echo "Git-Worktree ist nicht sauber. Bitte vorher committen oder staschen." >&2
    exit 1
  fi

  if [[ -n "$(git -C "$ROOT_DIR" ls-files --others --exclude-standard)" ]]; then
    echo "Untracked Dateien gefunden. Bitte vorher committen oder entfernen." >&2
    exit 1
  fi
}

require_main_branch() {
  local current_branch
  current_branch="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ "$current_branch" != "main" ]]; then
    echo "Releases sind nur auf Branch 'main' erlaubt. Aktueller Branch: ${current_branch:-unbekannt}" >&2
    exit 1
  fi
}

gh_safe() {
  env -u GITHUB_TOKEN gh "$@"
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || {
    echo "$tool wurde nicht gefunden." >&2
    exit 1
  }
}

ensure_version_not_exists() {
  if git -C "$ROOT_DIR" rev-parse -q --verify "refs/tags/$TAG_VERSION" >/dev/null 2>&1; then
    echo "Tag existiert lokal bereits: $TAG_VERSION" >&2
    exit 1
  fi

  if git -C "$ROOT_DIR" ls-remote --exit-code --tags origin "refs/tags/$TAG_VERSION" >/dev/null 2>&1; then
    echo "Tag existiert remote bereits: $TAG_VERSION" >&2
    exit 1
  fi

  if gh_safe release view "$TAG_VERSION" >/dev/null 2>&1; then
    echo "GitHub Release existiert bereits: $TAG_VERSION" >&2
    exit 1
  fi
}

update_version_files() {
  ROOT_DIR="$ROOT_DIR" TAG_VERSION="$TAG_VERSION" PLAIN_VERSION="$PLAIN_VERSION" python3 - <<'PY'
from pathlib import Path
import json
import os
import re

root = Path(os.environ["ROOT_DIR"])
tag_version = os.environ["TAG_VERSION"]
plain_version = os.environ["PLAIN_VERSION"]

(root / "VERSION").write_text(tag_version + "\n", encoding="utf-8")

pyproject_path = root / "pyproject.toml"
pyproject_text = pyproject_path.read_text(encoding="utf-8")
pyproject_text, pyproject_count = re.subn(
    r'(?m)^version = "[^"]+"$',
    f'version = "{plain_version}"',
    pyproject_text,
    count=1,
)
if pyproject_count != 1:
    raise SystemExit("Konnte pyproject.toml-Version nicht aktualisieren.")
pyproject_path.write_text(pyproject_text, encoding="utf-8")

for rel_path in ("package.json", "package-lock.json"):
    path = root / rel_path
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = plain_version
    if rel_path == "package-lock.json":
        data.setdefault("packages", {}).setdefault("", {})["version"] = plain_version
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

index_path = root / "public" / "index.html"
index_text = index_path.read_text(encoding="utf-8")
index_text, index_count = re.subn(
    r'(<a class="version-badge" id="app-version-badge" [^>]*>)(v[^<]+)(</a>)',
    r"\1" + tag_version + r"\3",
    index_text,
    count=1,
)
if index_count != 1:
    raise SystemExit("Konnte Fallback-Version in public/index.html nicht aktualisieren.")
index_path.write_text(index_text, encoding="utf-8")
PY
}

require_tool git
require_tool gh
require_tool python3
require_clean_worktree
require_main_branch
ensure_version_not_exists

update_version_files

git -C "$ROOT_DIR" add VERSION pyproject.toml package.json package-lock.json public/index.html
git -C "$ROOT_DIR" commit -m "Release $TAG_VERSION"
git -C "$ROOT_DIR" tag -a "$TAG_VERSION" -m "Release $TAG_VERSION"
git -C "$ROOT_DIR" push origin HEAD
git -C "$ROOT_DIR" push origin "$TAG_VERSION"
gh_safe release create "$TAG_VERSION" --repo MNLBCK/Platzbelegung --verify-tag --generate-notes --title "$TAG_VERSION"

echo "Release erstellt: $TAG_VERSION"
