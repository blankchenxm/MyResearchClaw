---
name: my-research-claw
description: >
  Codex skill index for academic paper scouting and deep reading. Use when the user wants
  to search top-conference papers by topic, track them in a persistent kanban, or deeply read
  one paper into structured DNL notes. Triggers include 搜论文, 顶会论文, find papers,
  conference papers, paper-reader, 精读论文, read this paper, and arXiv or DOI links with reading intent.
---

# MyResearchClaw

MyResearchClaw provides three project skills:

| Skill | Path | Use when |
|---|---|---|
| `conference-scout` | `skills/conference-scout/` | The user wants papers by topic, years, or venue groups |
| `paper-reader` | `skills/paper-reader/` | The user wants a single paper analyzed into DNL notes |
| `engineering-scout` | `skills/engineering-scout/` | The user wants implementation evidence, products, or real-world engineering signals for the topic |

## Routing

- Search, scouting, venue filtering, ranking, and kanban updates: use `conference-scout`.
- Reading notes, paper decomposition, note generation, and moving a paper into active reading: use `paper-reader`.
- Engineering implementations, GitHub repos, product signals, and deployment evidence: use `engineering-scout`.
- If the user asks for a broad research investigation on a topic, run `conference-scout` first and then `engineering-scout` for the same topic in the same turn unless the user explicitly wants papers only.
- If the user gives only a paper URL or arXiv ID with reading intent, go directly to `paper-reader`.

## Shared Output

- Database: `output/papers.json`
- Dashboard: `output/kanban.html`
- Topic paper page: `output/{topic_slug}-papers.html`
- Notes: `output/notes/{topic_slug}/`
- Topic engineering page: `output/{topic_slug}-engineering.html`

The repository keeps research state on disk, so preserve existing records unless the user explicitly asks to reset them.
