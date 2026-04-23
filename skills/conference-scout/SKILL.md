---
name: conference-scout
description: >
  Search for top-conference academic papers by topic, year range, and venue group, then update
  the persistent paper database and kanban dashboard. Use when the user asks to find papers,
  search top venues, compare conference coverage, or says phrases such as 搜论文, 顶会论文,
  find papers, conference papers, scout papers, or "[topic] papers in [conference]".
---

# Conference Scout

Goal: find top-venue papers on a topic, merge them into persistent project state, and regenerate `output/kanban.html`.

## Inputs

Extract:

| Field | Description | Default |
|---|---|---|
| `topic` | research topic, preferably English keywords | required |
| `year_start` | start year | `2022` |
| `year_end` | end year | current year |
| `conference_groups` | venue groups such as `ai_ml`, `iot_systems`, `security` | ask if missing |
| `specific_venues` | explicit venue override | optional |
| `output_html` | optional standalone HTML output path when the user wants a topic-specific page without overwriting the shared dashboard | optional |

If venue intent is missing, ask which venue family the user wants.

If the user asks for "顶会论文", "top venues", "完整调查", or otherwise signals completeness:

- do not silently narrow to a hand-picked subset of venues
- either ask for the venue family if truly ambiguous, or use the topic-to-venue profile rules below
- report the exact venue set you searched

## Topic-to-Venue Profiles

When the topic clearly falls into one of the following buckets, use the full profile by default instead of a partial subset:

```yaml
embedded_iot_firmware:
  - SenSys
  - IPSN
  - MobiSys
  - UbiComp / IMWUT
  - RTSS
  - EMSOFT
  - ASP-DAC
  - DATE
  - USENIX Security
  - NDSS

pcb_hardware_automation:
  - UIST
  - CHI
  - DAC
  - ICCAD
  - ASP-DAC
  - DATE
  - arXiv

embedded_ai_systems:
  - SenSys
  - IPSN
  - MobiSys
  - UbiComp / IMWUT
  - MobiCom
  - ASPLOS
  - EuroSys
  - OSDI
  - SOSP
```

Mapping rules:

- MCU firmware generation, auto flashing, embedded IoT software generation, cross-chip firmware adaptation:
  use `embedded_iot_firmware`
- PCB automation, schematic generation, board-level design automation, requirement-to-PCB:
  use `pcb_hardware_automation`
- If the topic spans multiple buckets, take the union instead of picking one narrow family

## Venue Groups

```yaml
ai_ml:
  - NeurIPS / Neural Information Processing Systems / NIPS
  - ICLR / International Conference on Learning Representations
  - ICML / International Conference on Machine Learning
  - AAAI
  - CVPR / Computer Vision and Pattern Recognition
  - ACL / Association for Computational Linguistics
  - EMNLP

iot_systems:
  - MobiCom / Mobile Computing and Networking
  - MobiSys / Mobile Systems
  - SenSys / Embedded Networked Sensor Systems
  - UbiComp / IMWUT / Interactive Mobile Wearable and Ubiquitous Technologies
  - IPSN

networking:
  - SIGCOMM
  - NSDI / Networked Systems Design
  - INFOCOM

systems:
  - OSDI / Operating Systems Design
  - SOSP / Operating Systems Principles
  - ATC / USENIX Annual Technical
  - EuroSys

security:
  - USENIX Security / USENIX Security Symposium
  - CCS / ACM Conference on Computer and Communications Security
  - IEEE S&P / IEEE Symposium on Security and Privacy
  - NDSS

hci:
  - CHI / ACM CHI Conference on Human Factors in Computing Systems
  - UIST / ACM Symposium on User Interface Software and Technology
  - CSCW / Computer-Supported Cooperative Work
```

## Data Sources

Priority order:

1. Semantic Scholar API
2. DBLP API
3. arXiv export API

Use DBLP as the fallback when Semantic Scholar is rate-limited or too sparse.

## Search Workflow

Conference-scout is not a one-shot batch pipeline anymore. It must behave like an iterative research agent:

- search once
- read what came back
- extract anchors
- decide the next query shape
- expand citations only after strong anchors exist
- assemble a timeline instead of returning a flat ranked list

You must explicitly log which round you are in.

### Round 1. Discovery

Purpose:

- find entry points, not final answers
- prioritize recent surveys, reviews, tutorials, and recent tier-1 papers with rich related-work sections
- discover the vocabulary the field actually uses

Queries:

- `{topic} survey`
- `{topic} review`
- `{topic} tutorial`
- `a survey of {topic}`
- if survey coverage is weak: recent tier-1 venue + topic + year

Tools:

- Semantic Scholar search
- DBLP search
- arXiv supplement only when venue coverage is sparse

Rules:

- do not stop after the first few hits
- if the topic is broad, use 1 to 2 wide discovery queries first
- when the user asked for top conferences, discovery still starts broad, but later rounds must tighten to tier-1 venue sweeps

### Round 2. Anchor Extraction

This is a required LLM reasoning step. Do not skip it.

After reading Round 1 results, produce an explicit JSON object:

```json
{
  "system_names": [],
  "author_names": [],
  "key_phrases": [],
  "datasets": [],
  "venue_year_pairs": [],
  "breakthrough_candidates": [],
  "survey_candidates": [],
  "constraint_terms": [],
  "negative_patterns": []
}
```

What to extract:

- system names, framework names, dataset names, benchmark names
- author names and `X et al.` patterns
- quoted or highly specific technical noun phrases
- explicit conference-year combinations such as `CVPR 2021`
- false-positive patterns from discovery results
- constraint terms that better describe the intended subproblem

Rules:

- system names should be used as quoted anchors in later rounds
- author names should trigger author-based search in Round 3
- key phrases should be quoted exactly when precise enough
- venue-year pairs should bypass fuzzy venue alias matching when possible

### Round 3. Precision Search

Purpose:

- convert Round 2 anchors into high-precision queries
- sweep top venues systematically instead of hoping a generic query surfaces the right paper

Query construction rules:

- system name: `"SystemName"`
- author-based: `"Author Name" {topic}`
- phrase-based: `"exact technical phrase"`
- venue-year-based: `{topic} {venue} {year}`
- context-constrained: `{topic} {constraint_term_1} {constraint_term_2}`

Top-venue rule:

- if the user wants top conferences, maintain explicit `tier_1` and optional `tier_2` venue lists
- tier 1 is the main sweep
- tier 2 is cross-check only unless the user asks for broader coverage

Venue execution rule:

- for recent work, do `venue × year` enumeration for the latest 2 years in range
- prefer DBLP venue listings when possible because venue membership is more reliable than Semantic Scholar aliases
- keep a per-venue completeness note so the user can see which venues were explicitly checked

### Round 4. Relevance Gate

This is another required LLM reasoning step.

Every candidate paper must pass a relevance rubric before entering the final pool.

Rubric:

1. Is the paper actually about the requested topic rather than a nearby but different subfield?
2. Does it match the intended context, device, population, or application scenario?
3. Does it meaningfully contribute to the field timeline rather than only sharing keywords?

Rules:

- reject candidates that only match broad keywords
- explicitly use `constraint_terms` and `negative_patterns` from Round 2
- venue membership alone is not enough; top venues still contain many off-topic papers

### Round 5. Citation Expansion

Only do this after Round 3 has found strong anchor papers.

Use:

- backward citations to find likely foundations and consolidation papers
- forward citations to find newer frontier follow-ups
- overlap across multiple frontier papers to detect shared milestone references

Heuristics:

- papers repeatedly cited by recent top papers are stronger foundation candidates
- papers described in related-work language as `first`, `seminal`, `foundational`, or `breakthrough` should be elevated
- papers between early foundational work and the newest frontier papers are consolidation candidates

### Round 6. Timeline Assembly

Do not use fixed year buckets such as `>5 years`.

Instead, classify by field role:

- `survey`
- `breakthrough`
- `foundation`
- `consolidation`
- `frontier`

Definitions:

- `breakthrough` / `foundation`: repeatedly cited anchors or papers described as seminal / first / foundational
- `consolidation`: papers that connect early foundations to current frontier threads
- `frontier`: recent top-venue papers representing the latest strong direction
- `survey`: papers that help explain the field map directly

Output should still appear on a continuous chronological timeline. Year is shown as metadata, but role is decided by the citation / related-work structure, not by rigid date thresholds.

### Round 7. Final Ranking

Ranking happens only after:

- anchor extraction
- relevance gating
- citation expansion
- timeline role assignment

Ranking priorities:

1. relevance to the exact topic and user constraints
2. timeline role usefulness
3. top-venue confirmation
4. recency for frontier papers
5. citations as a supporting signal only

Never let older high-citation loose matches crowd out clearly on-topic frontier papers.

## Latest-Paper Safeguard

When the user asks for recent or latest papers, you must verify whether the newest year in range has any venue-confirmed matches.

Checklist:

1. Check whether at least one target-venue paper from the newest year exists
2. If none appear, say that explicitly
3. If one exists, ensure it is not accidentally excluded by an incomplete venue set
4. In the response, mention concrete years, for example `SenSys 2026`, instead of vague wording like `latest`

## Summaries

For each retained paper, generate:

1. `summary_en`: 4 to 6 sentences on problem, approach, result, significance, and why it matters for the searched topic
2. `summary_zh`: 4 to 6 Chinese sentences covering the same substance with concrete technical detail

Rules:

- prefer concrete technical detail over generic praise
- mention at least one mechanism, metric, architecture choice, benchmark result, or deployment constraint when available
- make each summary readable as a compact research brief rather than a short abstract rewrite

## Persistent State

### `output/papers.json`

If missing, create:

```json
{
  "last_updated": "{TODAY}",
  "searches": [],
  "papers": []
}
```

For each new paper:

- deduplicate by `url`
- preserve existing `status`, `progress`, and `note_path`
- create new entries with `status: "unread"` only when absent

Suggested schema:

```json
{
  "id": "{SLUG}",
  "title": "Full paper title",
  "authors": "First Author et al.",
  "year": 2024,
  "venue": "IMWUT",
  "citations": 37,
  "url": "https://doi.org/...",
  "arxiv_id": "2401.XXXXX",
  "is_arxiv": false,
  "rank": 1,
  "timeline_role": "frontier",
  "timeline_reason_zh": "为什么它属于当前时间线节点",
  "summary_en": "...",
  "summary_zh": "...",
  "status": "unread",
  "progress": 0,
  "topic": "{TOPIC}",
  "date_added": "{TODAY}",
  "tags": [],
  "note_path": null
}
```

Additional rules:

- `timeline_role` must be one of `survey`, `breakthrough`, `foundation`, `consolidation`, `frontier`
- `timeline_reason_zh` should explain why the paper occupies that role in one concrete sentence
- if role confidence is weak, prefer `frontier` or `consolidation` over inventing certainty
- keep role assignment explainable from Round 4 and Round 5 evidence

Append each search to `searches` with topic, date, year range, venues, and `papers_added`.

### `output/kanban.html`

Load the dashboard template from `assets/kanban.html`.

Fill:

- `{{LAST_UPDATED}}`
- `{{ACTIVE_TOPIC}}`
- `{{ACTIVE_YEAR_RANGE}}`
- `{{ACTIVE_VENUES}}`
- `{{TIMELINE_ITEMS}}`
- `{{ALL_PAPERS}}`
- `{{ENGINEERING_LINK}}`

Render:

- a continuous timeline view ordered chronologically
- detailed paper cards that include each paper's `timeline_role`
- existing reading progress and note links when present

If the user explicitly asks for topic-specific standalone HTML that must not overwrite existing results:

- still update `output/papers.json`
- additionally generate a dedicated paper report HTML such as `output/projects/{topic_slug}/papers.html`
- use `assets/results.html` as the base template for that standalone report

## Response Format

Reply with a compact summary:

```text
Conference Scout — {TOPIC}
{YEAR_START}-{YEAR_END} | {VENUES}
{N} new papers added | {TOTAL} total tracked

Timeline:
- Survey: {N}
- Breakthrough / Foundation: {N}
- Consolidation: {N}
- Frontier: {N}

Key papers:
1. {Title} — {timeline_role} — {Venue} {Year}
   {timeline_reason_zh}

Supplements:
- {Title} — arXiv {Year}

Dashboard: output/kanban.html
```

## Template Assets

- Dashboard: `assets/kanban.html`
- Optional search report: `assets/results.html`

## Error Handling

| Error | Handling |
|---|---|
| Semantic Scholar `429` | switch to DBLP immediately |
| Semantic Scholar network failure | retry once, then DBLP |
| DBLP returns no relevant hits | try alternative keyword subsets |
| arXiv is noisy | filter aggressively by topic relevance |
| no venue-confirmed papers | show best unfiltered matches and mark them as fallback |
| malformed `papers.json` | recreate carefully and warn in the response |
