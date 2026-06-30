#!/bin/bash
# Install MyResearchClaw crontab entries on Linux.
# Run once: bash scripts/install-crontab.sh
# Safe to re-run — deduplicates existing entries.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3)"
LOG="$REPO_DIR/output/logs/queue-runner.log"

ENTRY="*/3 * * * * $PYTHON $REPO_DIR/scripts/queue-runner.py >> $LOG 2>&1"

# Remove any old version of this entry, then append fresh
( crontab -l 2>/dev/null | grep -v "queue-runner.py"; echo "$ENTRY" ) | crontab -

echo "✓ QRunner crontab installed (every 3 min):"
echo "  $ENTRY"
echo ""
echo "Verify with: crontab -l"
