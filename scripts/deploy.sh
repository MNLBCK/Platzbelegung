#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${1:-$ROOT_DIR/.deploy.local.env}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Konfigurationsdatei nicht gefunden: $CONFIG_FILE" >&2
  echo "Bitte deploy.example.env nach .deploy.local.env kopieren und anpassen." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Fehlende Variable in $CONFIG_FILE: $name" >&2
    exit 1
  fi
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

DEPLOY_METHOD="${DEPLOY_METHOD:-ftps}"
DEPLOY_PORT="${DEPLOY_PORT:-}"
DEPLOY_REMOTE_DIR="${DEPLOY_REMOTE_DIR:-}"
SCRAPE_BEFORE_UPLOAD="${SCRAPE_BEFORE_UPLOAD:-1}"
GENERATE_HTML="${GENERATE_HTML:-0}"
UPLOAD_CONFIG="${UPLOAD_CONFIG:-1}"
UPLOAD_HTACCESS="${UPLOAD_HTACCESS:-1}"
LFTP_VERIFY_CERTIFICATE="${LFTP_VERIFY_CERTIFICATE:-true}"

normalize_remote_path() {
  local path="$1"
  if [[ -z "$path" || "$path" == "/" ]]; then
    printf '/\n'
    return 0
  fi
  path="/${path#/}"
  path="${path%/}"
  printf '%s\n' "$path"
}

require_var DEPLOY_METHOD
require_var DEPLOY_HOST
require_var DEPLOY_REMOTE_DIR

DEPLOY_REMOTE_DIR="$(normalize_remote_path "$DEPLOY_REMOTE_DIR")"

case "$DEPLOY_METHOD" in
  ftp|ftps)
    require_var DEPLOY_USER
    require_var DEPLOY_PASS
    command -v lftp >/dev/null 2>&1 || {
      echo "lftp wurde nicht gefunden. Installation auf macOS z.B. mit: brew install lftp" >&2
      exit 1
    }
    ;;
  sftp|rsync)
    require_var DEPLOY_USER
    command -v ssh >/dev/null 2>&1 || {
      echo "ssh wurde nicht gefunden." >&2
      exit 1
    }
    command -v rsync >/dev/null 2>&1 || {
      echo "rsync wurde nicht gefunden." >&2
      exit 1
    }
    ;;
  *)
    echo "Unbekannte DEPLOY_METHOD-Option: $DEPLOY_METHOD" >&2
    echo "Erlaubt: ftp, ftps, sftp, rsync" >&2
    exit 1
    ;;
esac

cd "$ROOT_DIR"

resolve_platzbelegung_cmd() {
  if [[ -x "$ROOT_DIR/.venv/bin/platzbelegung" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/platzbelegung"
    return 0
  fi

  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "PYTHONPATH='$ROOT_DIR/src' '$ROOT_DIR/.venv/bin/python' -m platzbelegung.main"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "PYTHONPATH='$ROOT_DIR/src' python3 -m platzbelegung.main"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "PYTHONPATH='$ROOT_DIR/src' python -m platzbelegung.main"
    return 0
  fi

  if command -v platzbelegung >/dev/null 2>&1; then
    printf '%s\n' "platzbelegung"
    return 0
  fi

  return 1
}

PLATZBELEGUNG_CMD="$(resolve_platzbelegung_cmd || true)"
if [[ -z "$PLATZBELEGUNG_CMD" ]]; then
  echo "Konnte keinen ausführbaren Platzbelegung-CLI finden." >&2
  echo "Erwartet wurde eines von:" >&2
  echo "  - ./.venv/bin/platzbelegung" >&2
  echo "  - ./.venv/bin/python -m platzbelegung.main" >&2
  echo "  - python3 -m platzbelegung.main" >&2
  echo "  - globales 'platzbelegung'" >&2
  echo "Tipp: im Repo z.B. 'python3 -m pip install -e "'.[dev]'"' ausführen." >&2
  exit 1
fi

run_platzbelegung() {
  local subcommand="$1"
  shift || true
  # shellcheck disable=SC2086
  eval "$PLATZBELEGUNG_CMD" "$subcommand" "$@"
}

echo "==> Projektverzeichnis: $ROOT_DIR"
echo "==> Deploy-Methode: $DEPLOY_METHOD"
echo "==> Ziel: ${DEPLOY_HOST}:${DEPLOY_REMOTE_DIR}"
echo "==> Verwende CLI: $PLATZBELEGUNG_CMD"

if is_true "$SCRAPE_BEFORE_UPLOAD"; then
  echo "==> Erzeuge aktuellen Snapshot"
  run_platzbelegung scrape
fi

if is_true "$GENERATE_HTML"; then
  echo "==> Erzeuge HTML-Ausgabe"
  run_platzbelegung html
fi

if [[ ! -f "$ROOT_DIR/data/latest.json" ]]; then
  echo "data/latest.json fehlt. Bitte zuerst 'platzbelegung scrape' ausführen." >&2
  exit 1
fi

BASE_VERSION="$(tr -d '[:space:]' < "$ROOT_DIR/VERSION" 2>/dev/null || printf 'dev')"
DISPLAY_VERSION="$BASE_VERSION"
RELEASE_VERSION="$BASE_VERSION"
REPOSITORY_URL="https://github.com/MNLBCK/Platzbelegung"
DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BUILD_META_PATH="$ROOT_DIR/BUILD_META.json"
cleanup() {
  rm -f "$BUILD_META_PATH"
}
trap cleanup EXIT

if git -C "$ROOT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  if git -C "$ROOT_DIR" rev-parse -q --verify "refs/tags/$BASE_VERSION" >/dev/null 2>&1; then
    COMMITS_SINCE_RELEASE="$(git -C "$ROOT_DIR" rev-list --count "$BASE_VERSION..HEAD")"
    if [[ "$COMMITS_SINCE_RELEASE" -gt 0 ]]; then
      DISPLAY_VERSION="${BASE_VERSION}+${COMMITS_SINCE_RELEASE}"
    fi
  else
    LAST_TAG="$(git -C "$ROOT_DIR" describe --tags --abbrev=0 --match 'v*' 2>/dev/null || true)"
    if [[ -n "$LAST_TAG" ]]; then
      RELEASE_VERSION="$LAST_TAG"
      COMMITS_SINCE_RELEASE="$(git -C "$ROOT_DIR" rev-list --count "$LAST_TAG..HEAD")"
      if [[ "$COMMITS_SINCE_RELEASE" -gt 0 ]]; then
        DISPLAY_VERSION="${BASE_VERSION}+${COMMITS_SINCE_RELEASE}"
      fi
    fi
  fi
fi

RELEASE_URL="$REPOSITORY_URL"
if [[ -n "$RELEASE_VERSION" && "$RELEASE_VERSION" != "dev" ]]; then
  RELEASE_URL="$REPOSITORY_URL/releases/tag/$RELEASE_VERSION"
fi

DISPLAY_VERSION="$DISPLAY_VERSION" \
RELEASE_VERSION="$RELEASE_VERSION" \
REPOSITORY_URL="$REPOSITORY_URL" \
RELEASE_URL="$RELEASE_URL" \
DEPLOYED_AT="$DEPLOYED_AT" \
python3 - <<'PY' > "$BUILD_META_PATH"
import json
import os
print(json.dumps({
  "displayVersion": os.environ["DISPLAY_VERSION"],
  "releaseVersion": os.environ["RELEASE_VERSION"],
  "repositoryUrl": os.environ["REPOSITORY_URL"],
  "releaseUrl": os.environ["RELEASE_URL"],
  "deployedAt": os.environ["DEPLOYED_AT"],
}, ensure_ascii=False))
PY

echo "==> Build-Version: $DISPLAY_VERSION (Release-Basis: $RELEASE_VERSION)"

upload_with_lftp() {
  local protocol="$1"
  local port_part=""
  if [[ -n "$DEPLOY_PORT" ]]; then
    port_part=":$DEPLOY_PORT"
  fi

  local ssl_force="false"
  if [[ "$protocol" == "ftps" ]]; then
    ssl_force="true"
  fi

  local lftp_url="ftp://$DEPLOY_HOST$port_part"
  local remote_public_dir="$DEPLOY_REMOTE_DIR/public"
  local remote_data_dir="$DEPLOY_REMOTE_DIR/data"
  local create_root_dir=1
  if [[ "$DEPLOY_REMOTE_DIR" == "/" ]]; then
    remote_public_dir="/public"
    remote_data_dir="/data"
    create_root_dir=0
  fi

  local lftp_script
  lftp_script=$(cat <<EOF
set cmd:fail-exit true
set net:max-retries 2
set net:timeout 20
set ftp:passive-mode true
set ftp:ssl-force $ssl_force
set ssl:verify-certificate $LFTP_VERIFY_CERTIFICATE
lcd $ROOT_DIR
EOF
)

  lftp_script+=$'\n''set cmd:fail-exit false'
  if [[ "$create_root_dir" == "1" ]]; then
    lftp_script+=$'\n'"mkdir -p $DEPLOY_REMOTE_DIR"
  fi

  lftp_script+=$'\n'"mkdir -p $remote_public_dir"
  lftp_script+=$'\n'"mkdir -p $remote_data_dir"
  lftp_script+=$'\n''set cmd:fail-exit true'
  lftp_script+=$'\n'"mirror -R --verbose public $remote_public_dir"
  lftp_script+=$'\n'"put -O $DEPLOY_REMOTE_DIR backend.php"

  if is_true "$UPLOAD_CONFIG" && [[ -f "$ROOT_DIR/config.yaml" ]]; then
    lftp_script+=$'\n'"put -O $DEPLOY_REMOTE_DIR config.yaml"
  fi

  if is_true "$UPLOAD_HTACCESS" && [[ -f "$ROOT_DIR/.htaccess" ]]; then
    lftp_script+=$'\n'"put -O $DEPLOY_REMOTE_DIR .htaccess"
  fi

  if [[ -f "$ROOT_DIR/VERSION" ]]; then
    lftp_script+=$'\n'"put -O $DEPLOY_REMOTE_DIR VERSION"
  fi

  lftp_script+=$'\n'"put -O $DEPLOY_REMOTE_DIR BUILD_META.json"
  lftp_script+=$'\n'"put -O $remote_data_dir data/latest.json"

  if is_true "$GENERATE_HTML" && [[ -f "$ROOT_DIR/data/latest.html" ]]; then
    lftp_script+=$'\n'"put -O $remote_data_dir data/latest.html"
  fi

  lftp_script+=$'\nbye'

  lftp -u "$DEPLOY_USER","$DEPLOY_PASS" "$lftp_url" -e "$lftp_script"
}

upload_with_rsync() {
  local ssh_cmd="ssh"
  if [[ -n "$DEPLOY_PORT" ]]; then
    ssh_cmd+=" -p $DEPLOY_PORT"
  fi

  local remote="${DEPLOY_USER}@${DEPLOY_HOST}"

  echo "==> Lege Zielverzeichnisse an"
  $ssh_cmd "$remote" "mkdir -p '$DEPLOY_REMOTE_DIR/public' '$DEPLOY_REMOTE_DIR/data'"

  echo "==> Lade public/ hoch"
  rsync -av -e "$ssh_cmd" "$ROOT_DIR/public/" "$remote:$DEPLOY_REMOTE_DIR/public/"

  echo "==> Lade backend.php hoch"
  rsync -av -e "$ssh_cmd" "$ROOT_DIR/backend.php" "$remote:$DEPLOY_REMOTE_DIR/backend.php"

  if is_true "$UPLOAD_CONFIG" && [[ -f "$ROOT_DIR/config.yaml" ]]; then
    echo "==> Lade config.yaml hoch"
    rsync -av -e "$ssh_cmd" "$ROOT_DIR/config.yaml" "$remote:$DEPLOY_REMOTE_DIR/config.yaml"
  fi

  if is_true "$UPLOAD_HTACCESS" && [[ -f "$ROOT_DIR/.htaccess" ]]; then
    echo "==> Lade .htaccess hoch"
    rsync -av -e "$ssh_cmd" "$ROOT_DIR/.htaccess" "$remote:$DEPLOY_REMOTE_DIR/.htaccess"
  fi

  if [[ -f "$ROOT_DIR/VERSION" ]]; then
    echo "==> Lade VERSION hoch"
    rsync -av -e "$ssh_cmd" "$ROOT_DIR/VERSION" "$remote:$DEPLOY_REMOTE_DIR/VERSION"
  fi

  echo "==> Lade BUILD_META.json hoch"
  rsync -av -e "$ssh_cmd" "$BUILD_META_PATH" "$remote:$DEPLOY_REMOTE_DIR/BUILD_META.json"

  echo "==> Lade data/latest.json hoch"
  rsync -av -e "$ssh_cmd" "$ROOT_DIR/data/latest.json" "$remote:$DEPLOY_REMOTE_DIR/data/latest.json"

  if is_true "$GENERATE_HTML" && [[ -f "$ROOT_DIR/data/latest.html" ]]; then
    echo "==> Lade data/latest.html hoch"
    rsync -av -e "$ssh_cmd" "$ROOT_DIR/data/latest.html" "$remote:$DEPLOY_REMOTE_DIR/data/latest.html"
  fi
}

case "$DEPLOY_METHOD" in
  ftp)  upload_with_lftp ftp ;;
  ftps) upload_with_lftp ftps ;;
  sftp|rsync) upload_with_rsync ;;
esac

echo "==> Deploy abgeschlossen"
echo "Teste danach z.B.:"
echo "   /"
echo "   /api/demo"
echo "   /api/snapshot"
