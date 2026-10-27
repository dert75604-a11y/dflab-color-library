#!/usr/bin/env bash
# Copy ONLY the public color data onto the Aliyun nginx root.
# Never uploads index.html, nfc-scroll-assets, CNAME, or the rest of the repo.
# Never deploys to GitHub Pages.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_PATH="/var/www/shanghaidflab"
HOST="${DEPLOY_HOST:-106.15.198.252}"
PORT="${DEPLOY_PORT:-22}"
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" || "${DEPLOY_DRY_RUN:-}" == "1" ]]; then
  DRY_RUN=1
fi

if [[ "${DEPLOY_PATH:-/var/www/shanghaidflab}" != "/var/www/shanghaidflab" ]]; then
  echo "refuse: remote deploy path is fixed at /var/www/shanghaidflab" >&2
  exit 1
fi

COLORS_JSON="$ROOT/data/colors.json"
COLORS_DIR="$ROOT/assets/colors"
BRIDGE="$ROOT/assets/nfc-public-colors.js"

if [[ ! -f "$COLORS_JSON" || ! -f "$BRIDGE" ]]; then
  echo "refuse: missing $COLORS_JSON or $BRIDGE. Run the sync first." >&2
  exit 1
fi

if ! grep -q '"code"' "$COLORS_JSON"; then
  echo "note: data/colors.json has no public cards. This deploy clears assets/colors on the destination." >&2
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'dry-run:' >&2
    printf ' %q' "$@" >&2
    printf '\n' >&2
    return 0
  fi
  "$@"
}

copy_colors_local() {
  local dest="$1"
  mkdir -p "$dest/data" "$dest/assets/colors"
  cp "$COLORS_JSON" "$dest/data/colors.json"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$COLORS_DIR/" "$dest/assets/colors/"
  else
    find "$dest/assets/colors" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    cp -a "$COLORS_DIR/." "$dest/assets/colors/"
  fi
  cp "$BRIDGE" "$dest/assets/nfc-public-colors.js"
}

maybe_patch() {
  local index="$1"
  if [[ "${PATCH_NFC:-}" != "1" ]]; then
    return 0
  fi
  if [[ ! -f "$index" ]]; then
    echo "PATCH_NFC: no index at $index; left untouched" >&2
    return 0
  fi
  python3 "$ROOT/tools/patch_nfc_index.py" "$index"
}

if [[ "${DEPLOY_LOCAL:-}" == "1" ]]; then
  DEST="${DEPLOY_LOCAL_DIR:?Set DEPLOY_LOCAL_DIR to the nginx root you want to update}"
  echo "local copy -> $DEST (data/colors.json, assets/colors, nfc-public-colors.js)" >&2
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "dry-run: copy colors json, assets/colors, bridge into $DEST" >&2
    echo "dry-run: will not modify index.html unless PATCH_NFC=1 and the file is the NFC page" >&2
    exit 0
  fi
  copy_colors_local "$DEST"
  maybe_patch "$DEST/index.html"
  echo "local deploy done. index.html and nfc-scroll-assets were not replaced." >&2
  exit 0
fi

if [[ -z "${DEPLOY_SSH_USER:-}" ]]; then
  echo "Missing DEPLOY_SSH_USER. Remote deploy is to ${DEPLOY_SSH_USER:-<user>}@${HOST}:${REMOTE_PATH}." >&2
  echo "This environment has no SSH key that can log in. Set DEPLOY_SSH_USER and DEPLOY_SSH_KEY, or run on the server with DEPLOY_LOCAL=1." >&2
  exit 2
fi

SSH=(ssh -p "$PORT" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
RSYNC_SSH="ssh -p ${PORT} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
if [[ -n "${DEPLOY_SSH_KEY:-}" ]]; then
  SSH+=(-i "$DEPLOY_SSH_KEY")
  RSYNC_SSH+=" -i ${DEPLOY_SSH_KEY}"
fi
TARGET="${DEPLOY_SSH_USER}@${HOST}"

echo "remote copy -> ${TARGET}:${REMOTE_PATH} (data + assets/colors + bridge only)" >&2
run "${SSH[@]}" "$TARGET" "mkdir -p ${REMOTE_PATH}/data ${REMOTE_PATH}/assets/colors"
run rsync -a --delete -e "$RSYNC_SSH" "$COLORS_DIR/" "${TARGET}:${REMOTE_PATH}/assets/colors/"
run rsync -a -e "$RSYNC_SSH" "$COLORS_JSON" "${TARGET}:${REMOTE_PATH}/data/colors.json"
run rsync -a -e "$RSYNC_SSH" "$BRIDGE" "${TARGET}:${REMOTE_PATH}/assets/nfc-public-colors.js"

if [[ "${PATCH_NFC:-}" == "1" ]]; then
  TMP="$(mktemp)"
  trap 'rm -f "$TMP"' EXIT
  run "${SSH[@]}" "$TARGET" "cat ${REMOTE_PATH}/index.html" >"$TMP" || true
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "dry-run: would patch ${REMOTE_PATH}/index.html only to add assets/nfc-public-colors.js" >&2
  else
    python3 "$ROOT/tools/patch_nfc_index.py" "$TMP"
    run rsync -a -e "$RSYNC_SSH" "$TMP" "${TARGET}:${REMOTE_PATH}/index.html"
  fi
fi

echo "remote deploy done. NFC index is unchanged unless PATCH_NFC=1, and nfc-scroll-assets was not uploaded." >&2
