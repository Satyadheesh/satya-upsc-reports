#!/usr/bin/env bash
set -e

# ==============================================================================
# SatyaDheesh Autonomous Marketing Daemon (macOS Hands-Free Runner)
#
# Runs quietly in the background via launchd on your residential Mac IP.
# 1. Syncs pending drafts drafted by Gemma 4 12B from GitHub.
# 2. Quietly posts up to 2 queued comments via headless Playwright browser.
# 3. Updates the daily markdown report (queue/reports/YYYY-MM-DD.md).
# 4. Commits and syncs status back to GitHub.
# ==============================================================================

REPO_DIR="$HOME/.satya-marketing/repo"
VENV_PYTHON="$HOME/.satya-marketing/venv/bin/python3"
LOG_DIR="$HOME/.satya-marketing"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

echo "=== [$(date)] SatyaDheesh Background Poster Starting Cycle ==="

# 1. Check internet connectivity
if ! curl -s --head --max-time 5 https://www.google.com >/dev/null; then
    echo "[Daemon] No internet connection. Skipping cycle."
    exit 0
fi

# 2. Sync pending drafts from GitHub
echo "[Daemon] Syncing latest drafts from GitHub..."
git fetch origin marketing-agent 2>&1 || true
git pull origin marketing-agent --rebase 2>&1 || true

# 3. Check if there are pending drafts
PENDING_COUNT=$(find "$REPO_DIR/queue/pending" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
echo "[Daemon] Found $PENDING_COUNT pending draft(s) in queue."

if [ "$PENDING_COUNT" -eq 0 ]; then
    echo "[Daemon] No drafts pending. Sleeping until next cycle."
    exit 0
fi

# 4. Execute headless posting (policy: 2 YouTube comments + up to 3 other community comments)
echo "[Daemon] Launching headless posting agent..."
"$VENV_PYTHON" -m marketing.mac_poster --run --headless --max-youtube 2 --max-other 3

# 5. Sync queue changes and daily reports back to GitHub
if git status --porcelain | grep -q "queue/"; then
    echo "[Daemon] New posted items or reports detected. Syncing to GitHub..."
    git add queue/
    git commit -m "chore(marketing): sync posted drafts and daily report [skip ci]" || true
    git push origin marketing-agent || true
fi

echo "=== [$(date)] Cycle complete. Sleeping. ==="
