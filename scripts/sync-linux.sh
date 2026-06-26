#!/bin/bash
# Auto-pull on Linux — run via cron every minute.
# Pulls code + data (papers.json, notes, run_stats) from GitHub.
#
# Setup (run once):
#   chmod +x scripts/sync-linux.sh
#   crontab -e
#   Add: * * * * * /home/meng/Agent/MyResearchClaw/scripts/sync-linux.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$REPO_DIR/output/logs/sync-linux.log"
mkdir -p "$(dirname "$LOG")"
cd "$REPO_DIR" || exit 1

git fetch origin master --quiet 2>/dev/null || exit 0

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/master 2>/dev/null)
[ "$LOCAL" = "$REMOTE" ] && exit 0

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[${TIMESTAMP}] Pulling update $(git rev-parse --short origin/master)..." >> "$LOG"
git pull --ff-only origin master >> "$LOG" 2>&1
echo "[${TIMESTAMP}] Done." >> "$LOG"
