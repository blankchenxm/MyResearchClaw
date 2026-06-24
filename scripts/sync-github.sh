#!/bin/bash
# Periodic GitHub sync — called by launchd every 60 seconds.
# Pulls latest changes from origin/master and restarts serve.py if anything changed.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$REPO_DIR/output/logs/sync-github.log"

mkdir -p "$(dirname "$LOG")"

cd "$REPO_DIR" || exit 1

# Fetch silently; bail on network error without logging noise
git fetch origin master --quiet 2>/dev/null || exit 0

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/master 2>/dev/null)

[ "$LOCAL" = "$REMOTE" ] && exit 0

# New commits available — pull and restart
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pulling $(git rev-parse --short origin/master)..." >> "$LOG"
git pull --ff-only origin master >> "$LOG" 2>&1

# Restart serve.py via launchd (it will auto-respawn)
launchctl kickstart -k "gui/$(id -u)/com.myresearchclaw.serve" >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarted serve.py after update." >> "$LOG"
