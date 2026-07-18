#!/bin/bash
# MyResearchClaw — one-shot deploy script for macOS
#
# Usage (run from the repo root on your Mac mini):
#   chmod +x deploy.sh
#   ./deploy.sh
#
# What it does:
#   1. Finds (or creates) a Python env with PyMuPDF
#   2. Finds the Codex CLI and checks authentication
#   3. Writes .env with the discovered paths
#   4. Installs a LaunchAgent so serve.py starts on login and stays alive
#   5. Installs a LaunchAgent that auto-pulls from GitHub every 60 s
#   6. Patches your Cloudflare tunnel config to route a hostname → localhost:5678
#   7. Prints the URL you can use immediately

set -euo pipefail

###############################################################################
# Helpers
###############################################################################
BOLD=$(tput bold 2>/dev/null || true)
GREEN=$(tput setaf 2 2>/dev/null || true)
YELLOW=$(tput setaf 3 2>/dev/null || true)
RED=$(tput setaf 1 2>/dev/null || true)
RESET=$(tput sgr0 2>/dev/null || true)

info()  { echo "${GREEN}[✓]${RESET} $*"; }
warn()  { echo "${YELLOW}[!]${RESET} $*"; }
error() { echo "${RED}[✗]${RESET} $*"; exit 1; }
step()  { echo; echo "${BOLD}▶ $*${RESET}"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
SERVE_PLIST="$PLIST_DIR/com.myresearchclaw.serve.plist"
SYNC_PLIST="$PLIST_DIR/com.myresearchclaw.sync.plist"
ENV_FILE="$REPO_DIR/.env"
PORT="${MYRESEARCHCLAW_PORT:-5678}"

echo
echo "${BOLD}MyResearchClaw — macOS Deploy${RESET}"
echo "Repo: $REPO_DIR"
echo

###############################################################################
# Step 1 — Find Python with PyMuPDF (or create an env)
###############################################################################
step "Finding Python with PyMuPDF"

PYTHON=""

# Helper: test if a python binary has pymupdf
has_pymupdf() { "$1" -c "import fitz" 2>/dev/null; }

# Search existing conda envs
find_conda_python() {
    local conda_roots=(
        "$HOME/anaconda3"
        "$HOME/miniconda3"
        "$HOME/opt/anaconda3"
        "$HOME/opt/miniconda3"
        "/opt/homebrew/Caskroom/miniconda/base"
        "/opt/anaconda3"
    )
    for root in "${conda_roots[@]}"; do
        [ -d "$root/envs" ] || continue
        for env_dir in "$root/envs"/*/; do
            py="$env_dir/bin/python"
            [ -x "$py" ] || continue
            if has_pymupdf "$py"; then
                echo "$py"
                return 0
            fi
        done
        # Also check base env
        py="$root/bin/python"
        if [ -x "$py" ] && has_pymupdf "$py"; then
            echo "$py"
            return 0
        fi
    done
    return 1
}

PYTHON=$(find_conda_python 2>/dev/null || true)

if [ -n "$PYTHON" ]; then
    info "Found Python with PyMuPDF: $PYTHON"
else
    warn "No existing Python env has PyMuPDF. Creating a new conda env 'myresearchclaw'..."

    # Find conda
    CONDA_CMD=""
    for c in conda "$HOME/anaconda3/bin/conda" "$HOME/miniconda3/bin/conda" \
              "$HOME/opt/anaconda3/bin/conda" "$HOME/opt/miniconda3/bin/conda" \
              "/opt/homebrew/Caskroom/miniconda/base/bin/conda"; do
        command -v "$c" &>/dev/null && { CONDA_CMD="$c"; break; }
    done

    if [ -n "$CONDA_CMD" ]; then
        "$CONDA_CMD" create -n myresearchclaw python=3.10 -y -q
        CONDA_BASE=$("$CONDA_CMD" info --base 2>/dev/null | tr -d '[:space:]')
        PYTHON="$CONDA_BASE/envs/myresearchclaw/bin/python"
        "$PYTHON" -m pip install pymupdf requests --quiet
        info "Created conda env 'myresearchclaw': $PYTHON"
    else
        # Fallback: use brew / system python3 + pip
        PYTHON=$(command -v python3 || command -v python || error "No Python found. Install Python 3.10+ and re-run.")
        warn "No conda found — using $PYTHON. Installing pymupdf via pip..."
        "$PYTHON" -m pip install pymupdf requests --quiet --user
        info "Installed PyMuPDF into $PYTHON"
    fi
fi

###############################################################################
# Step 2 — Find Codex CLI
###############################################################################
step "Finding Codex CLI"

CODEX_BIN=$(command -v codex 2>/dev/null || true)

if [ -z "$CODEX_BIN" ]; then
    # Common install locations on macOS
    for candidate in \
        "$HOME/.local/bin/codex" \
        "/usr/local/bin/codex" \
        "/opt/homebrew/bin/codex"; do
        [ -x "$candidate" ] && { CODEX_BIN="$candidate"; break; }
    done
fi

if [ -z "$CODEX_BIN" ]; then
    error "Codex CLI not found. Install @openai/codex, run 'codex login', then re-run."
else
    info "Codex CLI: $CODEX_BIN ($("$CODEX_BIN" --version 2>/dev/null))"
    "$CODEX_BIN" login status >/dev/null 2>&1 \
        || error "Codex is not authenticated. Run 'codex login', then re-run."
    info "Codex authentication is configured"
fi

###############################################################################
# Step 3 — Write .env
###############################################################################
step "Writing .env"

cat > "$ENV_FILE" << EOF
# Auto-generated by deploy.sh — $(date '+%Y-%m-%d %H:%M:%S')
MYRESEARCHCLAW_PAPER_READER_PYTHON=$PYTHON
MYRESEARCHCLAW_CODEX_BIN=$CODEX_BIN
MYRESEARCHCLAW_CODEX_SEARCH=true
MYRESEARCHCLAW_CODEX_NETWORK=true
MYRESEARCHCLAW_PORT=$PORT
EOF

info "Written: $ENV_FILE"

###############################################################################
# Step 4 — Install LaunchAgent: serve.py (always-on)
###############################################################################
step "Installing serve.py LaunchAgent"

mkdir -p "$PLIST_DIR"
mkdir -p "$REPO_DIR/output/logs"

cat > "$SERVE_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.myresearchclaw.serve</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$REPO_DIR/serve.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$REPO_DIR/output/logs/serve.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/output/logs/serve.log</string>
    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
EOF

# Unload first if already loaded (ignore errors on first install)
launchctl unload "$SERVE_PLIST" 2>/dev/null || true
launchctl load "$SERVE_PLIST"
info "serve.py is running (auto-starts on login, auto-restarts on crash)"

###############################################################################
# Step 5 — Install LaunchAgent: GitHub sync (every 60 s)
###############################################################################
step "Installing GitHub auto-sync LaunchAgent"

chmod +x "$REPO_DIR/scripts/sync-github.sh"

cat > "$SYNC_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.myresearchclaw.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$REPO_DIR/scripts/sync-github.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$REPO_DIR/output/logs/sync.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/output/logs/sync.log</string>
</dict>
</plist>
EOF

launchctl unload "$SYNC_PLIST" 2>/dev/null || true
launchctl load "$SYNC_PLIST"
info "GitHub sync active — pulls every 60 s, restarts serve.py on new commits"

###############################################################################
# Step 6 — Cloudflare tunnel
###############################################################################
step "Configuring Cloudflare tunnel"

CF_CONFIG="$HOME/.cloudflared/config.yml"

if [ ! -f "$CF_CONFIG" ]; then
    warn "Cloudflare config not found at $CF_CONFIG — skipping tunnel setup."
    warn "Run deploy.sh again after setting up cloudflared."
else
    # Read tunnel name from the plist (Label's ProgramArguments last arg before 'run')
    TUNNEL_NAME=$(grep -A1 '"run"' /Library/LaunchDaemons/com.cloudflare.cloudflared.plist 2>/dev/null | grep '<string>' | sed 's/.*<string>\(.*\)<\/string>.*/\1/' | tail -1 || true)
    [ -z "$TUNNEL_NAME" ] && TUNNEL_NAME="crumb"

    # Ask for the hostname
    echo
    echo "  Your Cloudflare tunnel name: ${BOLD}$TUNNEL_NAME${RESET}"
    echo "  What hostname should MyResearchClaw be accessible at?"
    echo "  (e.g. research.yourdomain.com — must be a domain you control in Cloudflare)"
    echo -n "  Hostname: "
    read -r CF_HOSTNAME

    if [ -z "$CF_HOSTNAME" ]; then
        warn "No hostname entered — skipping Cloudflare config. Run deploy.sh again to set it up."
    else
        # Check if ingress rule already exists for this hostname
        if grep -q "$CF_HOSTNAME" "$CF_CONFIG" 2>/dev/null; then
            info "Ingress rule for $CF_HOSTNAME already in $CF_CONFIG"
        else
            # Backup the config
            cp "$CF_CONFIG" "${CF_CONFIG}.bak"
            info "Backed up config to ${CF_CONFIG}.bak"

            # Inject new ingress rule before the catch-all line
            # We use Python for reliable YAML editing (no external deps)
            python3 - "$CF_CONFIG" "$CF_HOSTNAME" "$PORT" << 'PYEOF'
import sys, re

config_path, hostname, port = sys.argv[1], sys.argv[2], sys.argv[3]
with open(config_path) as f:
    content = f.read()

new_rule = f"  - hostname: {hostname}\n    service: http://localhost:{port}\n"

# Insert before the catch-all (last ingress entry with no hostname)
if 'ingress:' in content:
    # Add before the last catch-all line (typically "  - service: http_status:404")
    content = re.sub(
        r'(ingress:.*?\n)((\s+-\s+service:\s+http_status:\d+))',
        lambda m: m.group(1) + new_rule + m.group(3),
        content,
        flags=re.DOTALL
    )
    if new_rule not in content:
        # Fallback: append to ingress block
        content = content.rstrip() + "\n" + new_rule + "  - service: http_status:404\n"
else:
    content += f"\ningress:\n{new_rule}  - service: http_status:404\n"

with open(config_path, 'w') as f:
    f.write(content)
print("ok")
PYEOF
            info "Added ingress rule: $CF_HOSTNAME → localhost:$PORT"
        fi

        # Create DNS CNAME record via cloudflared CLI
        if command -v cloudflared &>/dev/null; then
            echo "  Creating DNS record (this may take a moment)..."
            cloudflared tunnel route dns "$TUNNEL_NAME" "$CF_HOSTNAME" 2>&1 \
                && info "DNS record created: $CF_HOSTNAME" \
                || warn "DNS creation failed — create a CNAME manually: $CF_HOSTNAME → <tunnel-id>.cfargotunnel.com"
        else
            warn "cloudflared not in PATH — create the DNS CNAME manually in Cloudflare dashboard:"
            warn "  Name: $CF_HOSTNAME  →  Target: <tunnel-id>.cfargotunnel.com"
        fi

        # Restart cloudflared to pick up new config
        echo "  Restarting cloudflared..."
        sudo launchctl kickstart -k system/com.cloudflare.cloudflared 2>/dev/null \
            && info "cloudflared restarted" \
            || warn "Could not restart cloudflared automatically. Run: sudo launchctl kickstart -k system/com.cloudflare.cloudflared"

        # Save hostname to .env for reference
        echo "MYRESEARCHCLAW_HOSTNAME=https://$CF_HOSTNAME" >> "$ENV_FILE"
    fi
fi

###############################################################################
# Done
###############################################################################
echo
echo "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo "${GREEN}${BOLD}  MyResearchClaw is running!${RESET}"
echo
echo "  Local:   ${BOLD}http://localhost:$PORT${RESET}"
CF_HOST=$(grep "^MYRESEARCHCLAW_HOSTNAME=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
[ -n "$CF_HOST" ] && echo "  Remote:  ${BOLD}$CF_HOST${RESET}"
echo
echo "  serve.py logs:  $REPO_DIR/output/logs/serve.log"
echo "  Sync logs:      $REPO_DIR/output/logs/sync.log"
echo
echo "  To stop:   launchctl unload $SERVE_PLIST"
echo "  To start:  launchctl load $SERVE_PLIST"
echo "  To re-run: ./deploy.sh"
echo "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo
