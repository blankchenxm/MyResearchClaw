---
name: paper-reader
description: >
  Deep-read one academic paper from an arXiv URL, DOI, ACM URL, or bare arXiv ID, then generate
  structured DNL notes and update the persistent kanban state. Use when the user wants to read,
  analyze, summarize, or extract research insights from a specific paper, especially with phrases
  such as 精读, 帮我读, read this paper, paper notes, DNL, or when a paper link is given with reading intent.
---

# Paper Reader

Goal: analyze one paper, write a DNL note to `output/notes/`, update `output/papers.json`, and regenerate `output/kanban.html`.

Important language requirement:

- write the note body primarily in Chinese
- preserve paper titles, author names, venue names, and metric names in their original language when needed
- the explanatory prose, analysis, and section content should be Chinese-first so the in-page reader view is Chinese

## Supported Inputs

- `https://arxiv.org/abs/XXXX.XXXXX`
- `https://arxiv.org/pdf/XXXX.XXXXX`
- `https://doi.org/...`
- `https://dl.acm.org/doi/...`
- bare arXiv ID such as `2401.12345`

Treat bare arXiv IDs and `arxiv.org` URLs as arXiv papers. Everything else is DOI or landing-page based.

## Fetch Workflow

### 1. arXiv

Fetch:

1. `https://arxiv.org/abs/{ARXIV_ID}`
2. `https://arxiv.org/html/{ARXIV_ID}v1`

Extract title, authors, abstract, subjects, submission date, key figures, and accessible full-text sections.

If HTML is missing, continue with abstract-only analysis and state the limitation.

### 2. DOI / ACM / other

Fetch the landing page and extract title, authors, venue, year, and abstract.

Use Semantic Scholar metadata when it helps fill missing bibliographic fields, but do not fabricate unavailable full text.

## Match Existing State

Load `output/papers.json` and find the paper by:

1. exact `url`
2. matching `arxiv_id`
3. clear normalized-title match only if needed

If absent, create a new paper record during the save step.

## DNL Framework

Write the note using these sections:

1. Metadata
2. Why-read
3. CRGP: Context, Related work, Gap, Proposal
4. Figures
5. Experiments
6. Why it matters
7. Next steps
8. Scoring

Generate a short alias from the title for the note heading.

## Scoring

Use:

- Base: `1`
- Quality bonus: `0-2`
- Observation bonus: `0-2`

Final score = Base + Quality + Observation, maximum `5/5`.

Explain the arithmetic explicitly.

## Note Output

Write to:

```text
output/notes/{topic_slug}/{paper_id}.md
```

Use Markdown that stays readable in git and Obsidian. Prefer real numbers, concrete claims, and honest limitations.

Include at least one directly usable PDF link when available:

- arXiv: include the canonical PDF link
- DOI / ACM / project pages: include a PDF mirror or direct PDF link only when it is actually accessible
- if no PDF is available, say so explicitly instead of fabricating it

Suggested structure:

```markdown
# DNL 精读笔记 — {ALIAS}

## 0) Metadata
- **Title:** {FULL_TITLE}
- **Alias:** {ALIAS}
- **Authors / Org:** {AUTHORS}
- **Venue / Status:** {VENUE} ({YEAR})
- **Links:**
  - Paper: {URL}
  - HTML: https://arxiv.org/html/{ARXIV_ID}v1
  - PDF: https://arxiv.org/pdf/{ARXIV_ID}
- **Tags:** {TAGS}
- **My rating:** {N}/5

## 1) 一句话 Why-read
{ONE_PARAGRAPH}

## 2) CRGP 拆解 Introduction
...
```

## Persistent State Update

### `output/papers.json`

If the paper already exists:

- set `status` to `"reading"`
- set `note_path` to the saved note
- update `last_updated`
- include `pdf_url` when a reliable direct PDF link is available

If it does not exist:

- create a new entry with the available metadata
- set `status` to `"reading"`
- set `note_path` and derived tags
- include `pdf_url` when a reliable direct PDF link is available

### `output/kanban.html`

Load the dashboard template from `../conference-scout/assets/kanban.html` relative to this skill directory, then regenerate the dashboard with updated paper state.

## Response Format

Reply with a compact completion summary:

```text
DNL Complete — {ALIAS}
{TITLE}
{AUTHORS} | {VENUE} {YEAR} | {N}/5

Key finding: {WHY_READ}
Best result: {BEST_RESULT}
Insight: {TOP_INSIGHT}

Notes: output/notes/{paper_id}.md
If the paper belongs to a topic bucket, use the topic-scoped note path instead.
Dashboard: output/kanban.html
```

## Error Handling

| Error | Handling |
|---|---|
| arXiv HTML unavailable | continue with abstract page only |
| non-arXiv paper lacks full text | use abstract plus metadata and state the limit |
| paper absent from `papers.json` | create a new entry |
| malformed `papers.json` | recreate carefully and warn |
| no figures available | omit or explicitly mark the figure section |
