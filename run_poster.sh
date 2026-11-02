#!/usr/bin/env bash
set -e

# ==============================================================================
# SatyaDheesh Mac Manual Posting & Setup Runner
# Usage:
#   ./run_poster.sh --setup   # Opens browser window to log in to accounts once
#   ./run_poster.sh           # Runs manual posting session
# ==============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$HOME/.satya-marketing/venv/bin/python3"
cd "$REPO_DIR"

if [ "$1" == "--setup" ]; then
    echo "=== [SatyaDheesh Poster] Starting One-Time Account Login Setup ==="
    "$VENV_PYTHON" -m marketing.mac_poster --setup
    exit 0
fi

echo "=== [SatyaDheesh Poster] Syncing pending drafts from GitHub ==="
git fetch origin marketing-agent || true
git pull origin marketing-agent --rebase || true

echo "=== [SatyaDheesh Poster] Running Hands-free Posting Session ==="
"$VENV_PYTHON" -m marketing.mac_poster --run "$@"

# If any items were moved to posted/, commit and push
if git status --porcelain | grep -q "queue/"; then
    echo "=== [SatyaDheesh Poster] Syncing completed tasks back to GitHub ==="
    git add queue/
    git commit -m "marketing(queue): sync posted drafts and daily report [skip ci]" || true
    git push origin marketing-agent || true
fi

echo "=== [SatyaDheesh Poster] Session Complete ==="
