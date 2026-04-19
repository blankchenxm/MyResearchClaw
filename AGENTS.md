# MyResearchClaw Agents

## Intent

This repository is a research claw for two linked tasks:

1. Search top-venue papers by topic and year range.
2. Turn selected papers into persistent DNL reading notes.

## Authoritative Skill Entry Points

- `skills/conference-scout/SKILL.md`
- `skills/paper-reader/SKILL.md`
- `skills/engineering-scout/SKILL.md`

Use the `skills/` tree as the active Codex layout.

## Working Model

- `conference-scout` updates `output/papers.json`, regenerates `output/kanban.html`, and may generate topic-specific paper pages such as `output/{topic_slug}-papers.html`.
- `paper-reader` writes `output/notes/{topic_slug}/{paper_id}.md`, updates paper status, and regenerates the kanban.
- `engineering-scout` writes implementation-oriented results and may generate topic-specific engineering pages such as `output/{topic_slug}-engineering.html`.
- For broad topic investigation, run `conference-scout` and `engineering-scout` together unless the user explicitly narrows scope.
- Preserve existing paper state such as `status`, `progress`, and `note_path` unless the task explicitly changes them.

## GitHub Sync

- After each completed modification batch, commit the changes and push them to `origin/master`.
- Keep repository documentation in sync with this policy.

## Data Sources

Preferred order:

1. Semantic Scholar
2. DBLP
3. arXiv export API

For individual paper reads, arXiv, DOI landing pages, ACM DL, and Semantic Scholar metadata are all valid inputs.

## Output Conventions

- Keep notes as Markdown under `output/notes/{topic_slug}/`.
- Keep `output/kanban.html` as the default entry page. When multiple topics exist, it may act as a topic navigator instead of a single-topic paper board.
- Keep topic-specific paper pages under `output/{topic_slug}-papers.html`.
- Keep topic-specific engineering pages under `output/{topic_slug}-engineering.html`.
- Deduplicate papers primarily by URL and secondarily by stable identifiers such as arXiv ID.

## Runtime

- `serve.py` is the local Codex CLI-backed runtime for paper reading.
- It reads `skills/paper-reader/SKILL.md` as the active instruction source.
- Ensure the local `codex` CLI is available before starting the server.
