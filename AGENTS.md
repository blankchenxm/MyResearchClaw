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

- `conference-scout` updates `output/papers.json` and regenerates `output/kanban.html`.
- `paper-reader` writes `output/notes/{paper_id}.md`, updates paper status, and regenerates the kanban.
- `engineering-scout` writes `output/engineering.html` for implementation-oriented results on the current topic.
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

- Keep notes as Markdown under `output/notes/`.
- Keep the dashboard as a single generated file: `output/kanban.html`.
- Keep engineering output as a single generated file: `output/engineering.html`.
- Deduplicate papers primarily by URL and secondarily by stable identifiers such as arXiv ID.

## Runtime

- `serve.py` is the local OpenAI-backed runtime for paper reading.
- It reads `skills/paper-reader/SKILL.md` as the active instruction source.
- Configure `OPENAI_API_KEY` before starting the server.
