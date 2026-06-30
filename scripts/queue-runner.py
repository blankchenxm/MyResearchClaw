#!/usr/bin/env python3
"""
queue-runner.py — Periodically checks for rate-limited tasks and retries them.

Run via cron every 3 minutes:
  Mac: launchd plist (see config/com.myresearchclaw.queue-runner.plist)
  Linux: */3 * * * * /path/to/scripts/queue-runner.py

Only writes to log when it takes action (no heartbeat noise).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

PORT = 5001
BASE = f"http://localhost:{PORT}"
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "logs")
LOG_PATH = os.path.join(LOG_DIR, "queue-runner.log")


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def api_get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def api_post(path, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 0


def main():
    # 1. Check scout status
    scout = api_get("/api/scout-status")
    if scout:
        st = scout.get("status", "")
        err_type = scout.get("error_type", "")

        if st == "error" and err_type == "rate_limit":
            # Try to retry the scout (resumes from checkpoint if available)
            resp, code = api_post("/api/start-scout", {
                "topic": scout.get("topic", ""),
                "description": scout.get("description", ""),
                "year_start": scout.get("year_start", 2020),
                "year_end": scout.get("year_end", 2026),
                "venue_group": scout.get("venue_group", "ai_ml"),
                "specific_venues": scout.get("specific_venues", []),
            })
            if code == 200:
                log(f"Scout retry triggered: {scout.get('topic', '')} (was rate_limited)")
            else:
                log(f"Scout retry failed (code {code}): {scout.get('topic', '')}")
            time.sleep(10)
            # Verify it actually started
            scout2 = api_get("/api/scout-status")
            if scout2 and scout2.get("status") not in ("running_phase1", "running_phase2"):
                log(f"Scout did not start — still in state: {scout2.get('status')}")
            return  # One action per run to avoid double-triggering

        if st in ("running_phase1", "running_phase2"):
            # Scout is active — don't touch reader queue
            return

    # 2. Check reader queue — resume rate_limited papers
    from urllib.request import urlopen
    papers_resp = api_get("/api/papers")
    if not papers_resp:
        return

    papers = papers_resp.get("papers", [])
    resumable = [
        p for p in papers
        if p.get("status") == "error_resumable"
        and p.get("read_error_type") == "rate_limit"
    ]
    if resumable:
        p = resumable[0]
        resp, code = api_post("/api/read-paper", {
            "paper_id": p["id"],
            "url": p.get("url", ""),
            "title": p.get("title", ""),
        })
        if code == 200:
            result = resp or {}
            action = result.get("status", "?")
            log(f"Paper reader retry triggered ({action}): {p.get('title', p['id'])}")
        else:
            log(f"Paper reader retry failed (code {code}): {p.get('title', p['id'])}")
        return

    # 3. Nothing to do — stay silent
    return


if __name__ == "__main__":
    main()
