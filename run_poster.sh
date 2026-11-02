#!/usr/bin/env bash
set -e

# SatyaDheesh Mac Posting Runner
# Pulls latest drafts from marketing-agent branch, runs hands-free browser posting,
# and pushes posted status back to GitHub.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=== [SatyaDheesh Poster] Syncing pending drafts from GitHub ==="
git fetch origin marketing-agent || true
git pull origin marketing-agent --rebase || true

echo "=== [SatyaDheesh Poster] Running Hands-free Posting Session ==="
python3 -m marketing.mac_poster --run

# If any items were moved to posted/, commit and push
if git status --porcelain | grep -q "queue/"; then
    echo "=== [SatyaDheesh Poster] Syncing completed tasks back to GitHub ==="
    git add queue/
    git commit -m "marketing(queue): sync posted drafts [skip ci]" || true
    git push origin marketing-agent || true
fi

echo "=== [SatyaDheesh Poster] Session Complete ==="
