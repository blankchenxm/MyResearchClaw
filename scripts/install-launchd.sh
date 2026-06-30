#!/bin/bash
# Install (or update) all MyResearchClaw launchd agents on Mac mini.
# Run once: bash scripts/install-launchd.sh
# Safe to re-run — unloads existing agents before reinstalling.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_DIR"

PYTHON="$(command -v python3)"

###############################################################################
# Helper
###############################################################################
install_plist() {
  local label="$1" plist_path="$2" plist_content="$3"
  echo "$plist_content" > "$plist_path"
  launchctl unload "$plist_path" 2>/dev/null || true
  launchctl load -w "$plist_path"
  echo "✓ $label loaded"
}

###############################################################################
# 1. GitHub sync (every 60s) — may already exist; reinstall to pick up changes
###############################################################################
install_plist "sync-github" \
  "$LAUNCH_DIR/com.myresearchclaw.sync-github.plist" \
  "<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>             <string>com.myresearchclaw.sync-github</string>
  <key>ProgramArguments</key>
  <array>
    <string>$REPO_DIR/scripts/sync-github.sh</string>
  </array>
  <key>StartInterval</key>     <integer>60</integer>
  <key>RunAtLoad</key>         <true/>
  <key>StandardOutPath</key>   <string>$REPO_DIR/output/logs/sync-github.log</string>
  <key>StandardErrorPath</key> <string>$REPO_DIR/output/logs/sync-github.log</string>
</dict>
</plist>"

###############################################################################
# 2. QRunner (every 180s = 3 min)
###############################################################################
install_plist "queue-runner" \
  "$LAUNCH_DIR/com.myresearchclaw.queue-runner.plist" \
  "<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>             <string>com.myresearchclaw.queue-runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$REPO_DIR/scripts/queue-runner.py</string>
  </array>
  <key>StartInterval</key>     <integer>180</integer>
  <key>RunAtLoad</key>         <false/>
  <key>StandardOutPath</key>   <string>$REPO_DIR/output/logs/queue-runner.log</string>
  <key>StandardErrorPath</key> <string>$REPO_DIR/output/logs/queue-runner.log</string>
</dict>
</plist>"

echo ""
echo "All agents installed. Verify with:"
echo "  launchctl list | grep myresearchclaw"
