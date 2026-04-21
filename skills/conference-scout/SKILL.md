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

### 1. Semantic Scholar

Use:

```text
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={TOPIC_KEYWORDS}
  &fields=title,authors,year,venue,abstract,citationCount,externalIds,url
  &limit=50
  &year={YEAR_START}-{YEAR_END}
```

Rules:

- Run at most 2 queries.
- Venue filtering happens locally by alias matching on `paper.venue`.
- On `429`, skip directly to DBLP.
- On TLS or connection failure, retry once, then fall back to DBLP.
- On empty results, try one simplified query before falling back.

### 2. DBLP fallback

Use:

```text
GET https://dblp.org/search/publ/api?q={QUERY_TERMS}&format=json&h=30&f=0
```

Rules:

- Build 2 to 3 keyword-subset queries from the topic.
- Filter locally by venue aliases.
- DBLP records may lack abstract and citations; fill what is missing from Semantic Scholar only when easy and reliable.

### 2.5 Venue completeness check

After the initial Semantic Scholar / DBLP pass, run a targeted completeness check before final ranking.

Rules:

- For each venue in the chosen venue set, run one venue-aware verification query for the topic
- For recent years, explicitly verify the latest 2 years in range
- If a likely relevant paper is found in a target venue but was absent from the initial pool, add it
- Do not stop after one strong venue hit; completeness matters more than convenience for top-venue scouting

Examples:

- `AutoEmbed`-style failure to avoid:
  if the topic is MCU firmware automation and the venue profile includes `SenSys`, then recent `SenSys` papers must be checked explicitly instead of relying on a generic embedded query to surface them
- if the topic is PCB automation and the profile includes `DAC` and `ICCAD`, run explicit venue checks for both even if arXiv already has strong matches

### 3. arXiv supplement

Use only `export.arxiv.org` for the API:

```text
GET http://export.arxiv.org/api/query
  ?search_query=all:{TOPIC_KEYWORDS}
  &sortBy=submittedDate
  &sortOrder=descending
  &max_results=20
  &start=0
```

Keep up to 5 supplementary papers when:

- published year is within range
- title or abstract matches at least 2 topic keywords
- they are genuinely relevant, even if venue confirmation is missing

## Ranking

Use a simple additive score:

| Signal | Score |
|---|---|
| citationCount >= 100 | +3 |
| citationCount 50-99 | +2 |
| citationCount 10-49 | +1 |
| venue confirmed in target group | +2 |
| title contains exact topic phrase | +1.5 |
| abstract contains at least 3 topic keywords | +1 |
| year is the most recent year in range | +0.5 |
| arXiv-only result | -1 |

Return the best 8 venue-confirmed papers plus up to 3 arXiv supplements.

Important:

- ranking happens after completeness checking, not before
- never let high citations from older but looser matches crowd out clearly on-topic recent top-venue papers
- when the user asked for latest or recent work, bias toward the most recent venue-confirmed papers after relevance filtering

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

Append each search to `searches` with topic, date, year range, venues, and `papers_added`.

### `output/kanban.html`

Load the dashboard template from `assets/kanban.html`.

Fill:

- `{{LAST_UPDATED}}`
- `{{ACTIVE_TOPIC}}`
- `{{ACTIVE_YEAR_RANGE}}`
- `{{ACTIVE_VENUES}}`
- `{{ALL_PAPERS}}`
- `{{ENGINEERING_LINK}}`

Render cards for every paper. Use the paper's existing progress and note link when present.

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

Top confirmed papers:
1. {Title} — {Venue} {Year} — {citations}
   {summary_en}
   {summary_zh}

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
