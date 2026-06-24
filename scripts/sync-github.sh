#!/bin/bash
# Periodic GitHub sync — called by launchd every 60 seconds.
#
# Two-way sync:
#   PULL: code changes from origin/master → restart serve.py if updated
#   PUSH: server-generated data (papers.json, notes/) → commit + push to GitHub

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$REPO_DIR/output/logs/sync-github.log"

mkdir -p "$(dirname "$LOG")"
cd "$REPO_DIR" || exit 1

###############################################################################
# PUSH — commit any new server-generated data first
###############################################################################
git add \
    output/papers.json \
    output/notes/ \
    output/scout_status.json \
    output/token_usage.json \
    2>/dev/null || true

if ! git diff --cached --quiet 2>/dev/null; then
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    git commit -m "data: server update ${TIMESTAMP}" --quiet
    git push origin master --quiet >> "$LOG" 2>&1 \
        && echo "[${TIMESTAMP}] Pushed data update to GitHub" >> "$LOG"
fi

###############################################################################
# PULL — check for code changes
###############################################################################
git fetch origin master --quiet 2>/dev/null || exit 0

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/master 2>/dev/null)

[ "$LOCAL" = "$REMOTE" ] && exit 0

# New code commits — pull and restart serve.py
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pulling code update $(git rev-parse --short origin/master)..." >> "$LOG"
git pull --ff-only origin master >> "$LOG" 2>&1

launchctl kickstart -k "gui/$(id -u)/com.myresearchclaw.serve" >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarted serve.py after code update." >> "$LOG"
