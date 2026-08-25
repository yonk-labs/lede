#!/usr/bin/env sh
# One-command installer for lede (Mac/Linux).
#   curl -fsSL https://raw.githubusercontent.com/yonk-labs/lede/main/install.sh | sh
set -eu

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
    echo "error: python3 not found — install Python 3.10+ from https://python.org" >&2
    exit 1
fi

"$PY" -m pip install --user --upgrade lede

USER_BASE=$("$PY" -m site --user-base 2>/dev/null || true)
echo "lede installed. Run 'lede --help' to get started."
if [ -n "$USER_BASE" ]; then
    echo "If the 'lede' command isn't found, add $USER_BASE/bin to your PATH."
fi
