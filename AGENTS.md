# MyResearchClaw Codex Guidance

This repository is operated by the Codex CLI. The persistent dashboard and all
agentic server jobs are orchestrated by `serve.py`.

## Workflow routing

- Paper discovery server jobs: `serve.py` embeds the complete `conference-scout` contract in the
  initial Codex prompt. Follow that embedded contract; do not read repository Markdown through a
  shell command during the job.
- On Windows, never use `Get-Content`, `type`, `cat`, `rg`, `find`, or recursive repository
  inspection to load `SKILL.md`, `AGENTS.md`, `README.md`, or other local Markdown for a
  conference-scout server job. This avoids a PowerShell-to-Codex output hang.
- Deep reading: read and follow `skills/paper-reader/SKILL.md`.
- Engineering intelligence: read and follow `skills/engineering-scout/SKILL.md`.
- Shared architecture and dashboard behavior: consult the root `SKILL.md`.

For manually launched jobs outside `serve.py`, the caller may read the specific local skill file
named by the task. This does not apply to the server-run conference-scout path above, where the
contract is already embedded.

## Runtime

- Server: `python3 serve.py`
- Health: `curl http://localhost:5678/api/health`
- Paper-reader tests: `python3 -m pytest skills/paper-reader/tests`
- Codex jobs are non-interactive, use the Codex default model unless
  `MYRESEARCHCLAW_MODEL` is explicitly set, and have live web search enabled by
  default.

## Data safety

Preserve existing user-generated files under `output/`. Do not rewrite
generated dashboard HTML directly when `serve.py` can regenerate it from the
templates. Only one scout or reader job may run at a time.
