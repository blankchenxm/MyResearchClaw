---
name: conference-scout
description: >
  Search for academic papers by topic across top-conference venues, then organize results into
  a research timeline with four roles: survey, foundation/breakthrough, consolidation, and frontier.
  Timeline roles are determined by citation structure and related-work language, not fixed year
  thresholds. Use when the user asks to find papers, search top venues, map a research area,
  or says phrases such as 搜论文, 顶会论文, find papers, conference papers, scout papers,
  research timeline, or "[topic] papers in [conference]".
---

# Conference Scout

Goal: act as an iterative research agent — search, read, extract anchors, expand citations,
gate by relevance, then assemble a chronological timeline organized by each paper's role in
the field. Output a persistent paper database and regenerate `output/kanban.html`.

## Inputs

| Field | Description | Default |
|---|---|---|
| `topic` | research topic, preferably English keywords | required |
| `year_start` | start year for frontier search | auto-inferred from discovery |
| `year_end` | end year | current year |
| `venue_group` | venue group key from the venue registry below | ask if missing |
| `specific_venues` | explicit venue override, bypasses group selection | optional |
| `output_html` | standalone HTML output path for topic-specific page | optional |

If venue intent is missing, ask which venue family the user wants before proceeding.

If the user asks for "顶会论文", "top venues", "完整调查", or otherwise signals completeness:
- do not silently narrow to a hand-picked subset
- report the exact venue set searched in the response

---

## Venue Registry

Each venue group has two tiers. Tier 1 is the main sweep target. Tier 2 is used for
cross-checking only unless the user asks for broader coverage. Every venue entry includes
its DBLP listing URL for reliable venue-level completeness checks.

```yaml
wearable_sensing:
  tier_1:
    - name: UbiComp / IMWUT
      dblp: https://dblp.org/db/journals/imwut/
    - name: MobiCom
      dblp: https://dblp.org/db/conf/mobicom/
    - name: MobiSys
      dblp: https://dblp.org/db/conf/mobisys/
    - name: SenSys
      dblp: https://dblp.org/db/conf/sensys/
  tier_2:
    - name: IPSN
      dblp: https://dblp.org/db/conf/ipsn/
    - name: CHI
      dblp: https://dblp.org/db/conf/chi/
    - name: ISWC
      dblp: https://dblp.org/db/conf/iswc/
    - name: HotMobile
      dblp: https://dblp.org/db/conf/hotmobile/

ai_ml:
  tier_1:
    - name: NeurIPS
      dblp: https://dblp.org/db/conf/nips/
    - name: ICLR
      dblp: https://dblp.org/db/conf/iclr/
    - name: ICML
      dblp: https://dblp.org/db/conf/icml/
    - name: CVPR
      dblp: https://dblp.org/db/conf/cvpr/
  tier_2:
    - name: AAAI
      dblp: https://dblp.org/db/conf/aaai/
    - name: ACL
      dblp: https://dblp.org/db/conf/acl/
    - name: EMNLP
      dblp: https://dblp.org/db/conf/emnlp/

iot_systems:
  tier_1:
    - name: SenSys
      dblp: https://dblp.org/db/conf/sensys/
    - name: MobiSys
      dblp: https://dblp.org/db/conf/mobisys/
    - name: IPSN
      dblp: https://dblp.org/db/conf/ipsn/
    - name: UbiComp / IMWUT
      dblp: https://dblp.org/db/journals/imwut/
  tier_2:
    - name: MobiCom
      dblp: https://dblp.org/db/conf/mobicom/
    - name: EuroSys
      dblp: https://dblp.org/db/conf/eurosys/

security:
  tier_1:
    - name: USENIX Security
      dblp: https://dblp.org/db/conf/uss/
    - name: CCS
      dblp: https://dblp.org/db/conf/ccs/
    - name: IEEE S&P
      dblp: https://dblp.org/db/conf/sp/
    - name: NDSS
      dblp: https://dblp.org/db/conf/ndss/
  tier_2:
    - name: USENIX ATC
      dblp: https://dblp.org/db/conf/usenix/

systems:
  tier_1:
    - name: OSDI
      dblp: https://dblp.org/db/conf/osdi/
    - name: SOSP
      dblp: https://dblp.org/db/conf/sosp/
    - name: EuroSys
      dblp: https://dblp.org/db/conf/eurosys/
    - name: ASPLOS
      dblp: https://dblp.org/db/conf/asplos/
  tier_2:
    - name: USENIX ATC
      dblp: https://dblp.org/db/conf/usenix/
    - name: NSDI
      dblp: https://dblp.org/db/conf/nsdi/

hci:
  tier_1:
    - name: CHI
      dblp: https://dblp.org/db/conf/chi/
    - name: UIST
      dblp: https://dblp.org/db/conf/uist/
  tier_2:
    - name: CSCW
      dblp: https://dblp.org/db/conf/cscw/
    - name: IUI
      dblp: https://dblp.org/db/conf/iui/
```

### Topic-to-Venue Mapping

When the topic clearly fits a profile, auto-select it instead of asking:

- wearable sensing, ExG, EEG/EMG sensing, auditory wearables, AR glasses audio → `wearable_sensing`
- MCU firmware, embedded IoT software, cross-chip adaptation → `embedded_iot_firmware`
- machine learning, deep learning, representation learning → `ai_ml`
- sensor systems, mobile systems, IoT platforms → `iot_systems`
- adversarial attacks, sensor security, side channels → `security` + `iot_systems`
- OS, storage, distributed systems → `systems`
- human-computer interaction, user interfaces → `hci`
- topic spans multiple buckets → take the union of relevant tier-1 lists

---

## Data Sources

Priority order:
1. DBLP venue listing (most reliable for venue membership)
2. Semantic Scholar API (abstract, citations, references)
3. arXiv export API (supplement only)

### DBLP Venue Listing

Use this to check venue completeness for specific years. Query pattern:

```
GET https://dblp.org/search/publ/api
  ?q={TOPIC_KEYWORDS}+venue:{VENUE_NAME}
  &format=json
  &h=30
```

Or fetch the DBLP venue page directly to get the full paper list for a given year:
`{dblp_url}` + year suffix, e.g. `https://dblp.org/db/conf/sensys/sensys2024.html`

DBLP venue fields are human-maintained and far more reliable than Semantic Scholar's
auto-assigned venue strings. Always prefer DBLP for answering "did this paper appear
in this venue?"

### Semantic Scholar API

```
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={TOPIC_KEYWORDS}
  &fields=title,authors,year,venue,abstract,citationCount,influentialCitationCount,
          externalIds,url,references,citations
  &limit=50
  &year={YEAR_START}-{YEAR_END}
```

Use `influentialCitationCount` (not just `citationCount`) when assessing whether a paper
is a genuine foundation. Highly cited papers with low `influentialCitationCount` are
likely survey-inflated and should not be elevated to foundation status.

Reference and citation expansion:
```
GET https://api.semanticscholar.org/graph/v1/paper/{id}/references
  ?fields=title,authors,year,venue,citationCount,influentialCitationCount
  &limit=50

GET https://api.semanticscholar.org/graph/v1/paper/{id}/citations
  ?fields=title,authors,year,venue,citationCount
  &limit=50
```

On `429`: switch to DBLP immediately. On network failure: retry once, then DBLP.

### arXiv Supplement

```
GET http://export.arxiv.org/api/query
  ?search_query=all:{TOPIC_KEYWORDS}
  &sortBy=submittedDate
  &sortOrder=descending
  &max_results=20
```

Keep arXiv results only when:
- published year is within range
- title or abstract matches at least 2 topic-specific (non-generic) keywords
- no venue-confirmed version exists for the same work

---

## Search Workflow

This skill is an iterative research agent. You must log which round you are in.
Do not skip rounds. Do not merge rounds.

---

### Round 1 — Discovery

Purpose: find entry points and field vocabulary, not final answers.

Queries to run (in order, stop early if rich survey coverage is found):

1. `{topic} survey`
2. `{topic} review`
3. `{topic} tutorial`
4. `a survey of {topic}`
5. If survey coverage is weak: `{topic}` scoped to the most relevant tier-1 venue + recent year

Rules:
- read the abstracts and related-work hints in what comes back
- note which subfield vocabulary appears (system names, task names, metric names)
- do not filter by venue in this round — discovery is intentionally broad
- if multiple distinct subfields appear, note the boundary so Round 2 can set constraints

---

### Round 2 — Anchor Extraction  *(LLM reasoning step — no API call)*

Read all Round 1 results and produce this JSON before proceeding:

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
  "negative_patterns": [],
  "subfield_boundary": ""
}
```

Field guidance:

- `system_names`: proper-noun system/framework/model names seen in results; use as quoted anchors
- `author_names`: recurring author names; trigger author-based search in Round 3
- `key_phrases`: technical noun phrases specific enough to quote; avoid generic words
- `venue_year_pairs`: explicit conference-year pairs found (e.g. `["SenSys 2023", "IMWUT 2024"]`)
- `breakthrough_candidates`: papers described with language like "first", "seminal", "foundational",
  "the first to", "pioneering", "introduced the concept of"
- `survey_candidates`: papers that appear to be surveys or tutorials
- `constraint_terms`: 1–2 words that narrow the topic to the intended subproblem
- `negative_patterns`: recurring false-positive patterns to exclude in Round 4
  (e.g. "industrial control systems" if topic is wearables, not SCADA)
- `subfield_boundary`: one sentence describing where the intended topic ends and adjacent
  fields begin; used as the Round 4 relevance rubric anchor

---

### Round 3 — Precision Search

Purpose: convert anchors into high-precision queries and sweep tier-1 venues systematically.

Query types (run all that apply given Round 2 anchors):

| Anchor type | Query form |
|---|---|
| system name | `"SystemName"` |
| author name | `"Author Name" {topic}` |
| key phrase | `"exact technical phrase" {context}` |
| venue + year | `{topic} {constraint_terms}` scoped to `{venue} {year}` |
| constraint | `{topic} {constraint_term_1} {constraint_term_2}` |

Venue sweep rule:

- for the latest 2 years: enumerate `tier_1 venue × year` explicitly
- use DBLP venue listing pages (`{dblp_url}`) to confirm membership when Semantic Scholar
  venue strings are ambiguous or missing
- record a per-venue completeness note: which venues were explicitly checked and for which years

Do not rely on Semantic Scholar's `venue` field alone for tier-1 confirmation. If a
paper's venue field is missing or ambiguous, check DBLP by DOI or title search.

---

### Round 4 — Relevance Gate  *(LLM reasoning step — no API call)*

Every candidate paper must pass this rubric before entering the pool.
Apply `constraint_terms` and `negative_patterns` from Round 2 explicitly.

Questions to answer for each paper (all three must be yes):

1. Is this paper about the specific subproblem, or only about a nearby field that shares keywords?
   Use `subfield_boundary` from Round 2 as the reference line.
2. Does the paper match the intended context — device type, application scenario, population,
   or system layer — that the user is researching?
3. Does the paper contribute meaningfully to the timeline, or does it only share surface keywords?

Rejection rules:

- reject if the paper matches `negative_patterns` from Round 2
- reject if the paper's primary contribution is clearly outside `subfield_boundary`
- reject if the paper is a workshop version of a venue-confirmed paper already in the pool
- venue membership alone is not sufficient — top venues contain many off-topic papers

---

### Round 5 — Citation Expansion

Only run after Round 3 has produced at least 3 anchor papers that passed Round 4.

Steps:

1. For each top-3 frontier paper from Round 3, fetch its `references` via Semantic Scholar
2. Collect the union of all references; sort by frequency of co-occurrence across the 3 papers
3. Papers co-cited by 2 or more frontier papers are strong foundation / consolidation candidates
4. For each top-3 anchor paper, fetch its `citations`; sort by year descending
5. Recent papers in the citations list that also appear in tier-1 venues are new frontier candidates

Foundation elevation rules:

- papers described as "first", "seminal", "foundational", "introduced", or "pioneering" in the
  related-work sections of multiple frontier papers → promote to `breakthrough` or `foundation`
- papers with high `influentialCitationCount` relative to total `citationCount` → stronger
  foundation signal
- papers that bridge the earliest foundational work and the current frontier → `consolidation`

---

### Round 6 — Timeline Assembly

Classify every paper that passed Round 4 into exactly one role:

| Role | Definition |
|---|---|
| `survey` | papers that provide a field-wide literature map |
| `breakthrough` | papers described as seminal / first / foundational by the community; introduced a key concept or technique |
| `foundation` | early core papers that established the baseline the field builds on; may overlap with breakthrough |
| `consolidation` | papers between the earliest foundations and the current frontier; show how the field branched |
| `frontier` | recent tier-1 papers representing the current strongest direction |

Rules:

- role is determined by citation structure and related-work language, not by year
- a 2023 paper can be a breakthrough if it introduced a concept the rest of the field treats as foundational
- a 2019 paper can be frontier if the field is young and recent work still cites it as state-of-the-art
- if role confidence is low, prefer `consolidation` over inventing certainty
- year is metadata on the timeline, not the classification criterion

Output order: sort chronologically by year within and across roles.
The timeline is continuous; the role label is an annotation, not a section break.

---

### Round 7 — Final Output

Ranking priority within each role:

1. Relevance to the exact topic and user constraints (from Round 4 rubric)
2. Timeline role usefulness (breakthrough > consolidation > frontier for foundational context;
   frontier > consolidation for latest-work queries)
3. Tier-1 venue confirmation
4. Recency (for frontier), `influentialCitationCount` (for foundation/breakthrough)
5. Raw `citationCount` as a weak supporting signal only

Target counts per search:
- `survey`: 1–3
- `breakthrough` / `foundation`: 2–4
- `consolidation`: 3–5
- `frontier`: 4–8
- arXiv supplements (no venue): up to 3, clearly labeled

Never let high-citation older loose matches crowd out clearly on-topic recent tier-1 papers.

---

## Latest-Paper Safeguard

When the user asks for recent or latest papers:

1. Verify at least one tier-1 paper from the newest year in range exists
2. If none found, say so explicitly and report what the most recent tier-1 result was
3. Reference concrete years in the response (e.g. `SenSys 2025`) — never just say "latest"
4. Do not let this safeguard be satisfied by a tier-2 venue hit if tier-1 was checked and came up empty

---

## Summaries

For each retained paper, generate:

- `summary_en`: 4–6 sentences covering problem, approach, result, significance, and why it
  matters for the searched topic
- `summary_zh`: 4–6 Chinese sentences covering the same substance with concrete technical detail

Rules:
- prefer concrete technical detail over generic praise
- mention at least one: mechanism, metric, architecture choice, benchmark result, deployment constraint
- write as a compact research brief, not an abstract rewrite
- for `survey` papers, summarize the taxonomy or periodization the survey imposes on the field

---

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

Paper schema:

```json
{
  "id": "{SLUG}",
  "title": "Full paper title",
  "authors": "First Author et al.",
  "year": 2024,
  "venue": "IMWUT",
  "venue_tier": 1,
  "citations": 37,
  "influential_citations": 12,
  "url": "https://doi.org/...",
  "arxiv_id": "2401.XXXXX",
  "is_arxiv": false,
  "timeline_role": "frontier",
  "timeline_reason_zh": "首次在 AR 眼镜上实现了端侧 neural beamforming，被后续工作广泛引用",
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

Field rules:
- `timeline_role`: one of `survey`, `breakthrough`, `foundation`, `consolidation`, `frontier`
- `timeline_reason_zh`: one concrete sentence explaining the role assignment
- `venue_tier`: 1, 2, or 0 for arXiv/unconfirmed
- `influential_citations`: from Semantic Scholar `influentialCitationCount`; set to null if unavailable
- deduplication by `url`; preserve existing `status`, `progress`, `note_path` on re-search

Append each search to `searches`:

```json
{
  "topic": "...",
  "date": "...",
  "year_range": "...",
  "venues_checked": ["SenSys 2024", "SenSys 2025", "IMWUT 2024", "..."],
  "papers_added": 7
}
```

### `output/kanban.html`

Load the dashboard template from `assets/kanban.html`.

Fill:
- `{{LAST_UPDATED}}`
- `{{ACTIVE_TOPIC}}`
- `{{ACTIVE_YEAR_RANGE}}`
- `{{ACTIVE_VENUES}}`
- `{{TOTAL_PAPERS}}`
- `{{TIMELINE_SPAN}}`
- `{{SURVEY_COUNT}}`
- `{{BREAKTHROUGH_COUNT}}`
- `{{CONSOLIDATION_COUNT}}`
- `{{FRONTIER_COUNT}}`
- `{{OVERVIEW_ZH}}`
- `{{OVERVIEW_EN}}`
- `{{TIMELINE_ITEMS}}`
- `{{ENGINEERING_LINK}}`

Render:
- an opening overview paragraph summarizing total paper count and role breakdown
- a continuous chronological timeline with role annotations
- paper cards showing `timeline_role`, bilingual role reasoning, reading progress, and note links
- venue tier badge on each card

If the user requests topic-specific standalone HTML:
- still update `output/papers.json`
- generate `output/projects/{topic_slug}/papers.html` using `assets/kanban.html` as the base layout
- do not overwrite the shared dashboard

---

## Response Format

```
Conference Scout — {TOPIC}
{YEAR_RANGE_INFERRED} | {VENUES_CHECKED}

Rounds completed: Discovery → Anchors → Precision → Relevance Gate → Citation Expansion → Timeline

{N} new papers added | {TOTAL} total tracked

Timeline summary:
  Survey:               {N}
  Breakthrough/Found.:  {N}
  Consolidation:        {N}
  Frontier:             {N}
  arXiv supplement:     {N}

Key papers by timeline role:

[Foundation / Breakthrough]
1. {Title} ({Venue} {Year}, {citations} citations)
   Role: {timeline_reason_zh}
   {summary_zh}

[Consolidation]
2. {Title} ({Venue} {Year})
   Role: {timeline_reason_zh}
   {summary_zh}

[Frontier]
3. {Title} ({Venue} {Year})
   Role: {timeline_reason_zh}
   {summary_zh}

Venues explicitly checked:
  Tier 1: SenSys 2024/2025, IMWUT 2024/2025, MobiCom 2024/2025, MobiSys 2024/2025
  Tier 2: (cross-check only)

Dashboard: output/kanban.html
```

---

## Error Handling

| Error | Action |
|---|---|
| Semantic Scholar `429` | switch to DBLP immediately |
| Semantic Scholar network failure | retry once, then DBLP |
| DBLP venue page unavailable | fall back to DBLP search API with venue keyword |
| No venue-confirmed papers found | show best unfiltered matches, mark as unconfirmed |
| arXiv results are noisy | filter aggressively; require ≥2 non-generic topic keyword matches |
| `papers.json` malformed | recreate with warning; do not silently overwrite existing data |
| Round 4 rejects >80% of candidates | warn the user; loosen one constraint and re-gate |
