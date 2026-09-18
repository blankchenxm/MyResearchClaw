# MyResearchClaw Codex Guidance

This repository is operated by the Codex CLI. The persistent dashboard and all
agentic server jobs are orchestrated by `serve.py`.

## Workflow routing

- Paper discovery: read and follow `skills/conference-scout/SKILL.md`.
- On Windows, do not dump full SKILL files through `powershell.exe -Command Get-Content -Raw`;
  the server prompt embeds the required conference-scout workflow, and targeted reads or web search
  should be used instead to avoid a large PowerShell-to-Codex output hang.
- Deep reading: read and follow `skills/paper-reader/SKILL.md`.
- Engineering intelligence: read and follow `skills/engineering-scout/SKILL.md`.
- Shared architecture and dashboard behavior: consult the root `SKILL.md`.

Do not assume that a repository-local skill is installed globally. Read the
specific `SKILL.md` path named by the task before executing its workflow.

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
