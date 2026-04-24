---
name: engineering-scout
description: >
  Search engineering implementations for a research topic across GitHub, products, startups,
  and technical media. Organized into three distance rings: paper-linked implementations,
  independent engineering solutions, and industry/ecosystem signals. Uses iterative query
  refinement to avoid false positives. Use when the user wants to know whether a topic has
  open-source implementations, commercial products, or real-world deployment signals, or says
  phrases such as 工程实现, 开源项目, GitHub 搜索, 有没有产品, 行业动态, find implementations,
  engineering scout, or "how is X implemented in practice".
---

# Engineering Scout

Goal: for a research topic, collect implementation-oriented evidence organized into three
distance rings, then generate `output/engineering.html`. Operates as an iterative search
agent — never a single-shot batch query.

---

## Inputs

| Field | Description | Default |
|---|---|---|
| `topic` | engineering topic or the same topic used in conference-scout | required |
| `year_start` | start year for recency filtering | auto-inferred |
| `year_end` | end year | current year |
| `focus` | optional filter: `github`, `products`, `news`, `all` | `all` |
| `paper_anchors` | system names / author names / arXiv IDs from a prior paper search | from context |
| `output_html` | standalone HTML output path | optional |

If the user runs this immediately after conference-scout, automatically inherit:
- `topic` from the last paper search
- `paper_anchors` from any system names, author names, or arXiv IDs found in that search

---

## Three-Ring Search Model

Organize all results into rings by distance from the core topic. Search rings in order.
Do not jump to ring 3 before ring 1 and 2 are reasonably covered.

```
Ring 1 — Paper-Linked Implementations
  Repos and artifacts directly produced by the research papers on this topic.
  Highest quality signal: paper authorship is a quality filter.

Ring 2 — Independent Engineering Solutions
  GitHub projects and products solving the same problem independently.
  Assess maturity, adoption, and architectural approach.

Ring 3 — Ecosystem and Industry Signals
  News, startup activity, technical blogs, community discussions,
  product launches, and adoption stories.
  Use to judge where the field sits on the research-to-deployment spectrum.
```

---

## Query Decomposition  *(do this before any search)*

Before running any queries, decompose the topic into three dimensions:

```
problem:    what is being solved (noun phrase describing the challenge)
action:     the automated/engineered operation being performed (verb phrase)
artifact:   what the solution produces or consists of (tool / framework / system / pipeline)
```

Then generate queries by combining dimensions, not by using the topic string directly.

Example:
```
topic: "自动烧入PCB固件"

problem:    firmware flashing for embedded devices
action:     automated / CI/CD / orchestrated / batch / OTA
artifact:   tool / pipeline / framework / workflow / system

generated queries:
  - "firmware flashing automation tool" github
  - "automated firmware deployment pipeline embedded"
  - "OTA firmware CI/CD embedded systems"
  - firmware flash orchestration stars:>50
  - "auto flash" embedded microcontroller site:github.com
```

This decomposition is the primary defense against false positives like returning
ESP-IDF documentation when the user wants tools that automate ESP-IDF.

The problem/action/artifact split must be written down before Round 1 begins.

---

## Search Workflow

Engineering-scout is an iterative agent. Log which round you are in.
Do not skip rounds. Never emit final results before Round 4.

---

### Round 1 — Broad Discovery

Purpose: surface the vocabulary and false-positive landscape before committing to precise queries.

**Ring 1 queries (paper-linked):**

If `paper_anchors` are available from a prior conference-scout run:
- `"{system_name}" github` — one query per system name
- `"{paper_title}" implementation` — for top 2-3 papers
- `"{author_name}" {topic} code` — for known authors with public repos
- `site:github.com {arXiv_id}` — if arXiv IDs are known

If no paper anchors are available, skip Ring 1 for now and note it as incomplete.

**Ring 2 queries (independent implementations):**

Use the decomposed `problem + action + artifact` queries from Query Decomposition.
Run 3-4 queries, not all permutations.

**GitHub-specific tactics:**

- Topic tags: `topic:{relevant-tag}` — e.g. `topic:firmware-update topic:ota`
  (tag search targets author-labeled repos, far more precise than keyword search)
- Stars filter: `stars:>50 pushed:>{YEAR_START}-01-01` to exclude abandoned projects
- Awesome lists: search `awesome-{topic}` — curated lists exist for most active subfields
- HuggingFace: for AI/ML topics, search `huggingface.co/models` and `huggingface.co/spaces`

**Ring 3 queries (ecosystem signals):**

- `{topic} startup funding`
- `{topic} product launch site:techcrunch.com OR site:venturebeat.com`
- `{topic} blog post technical implementation`
- `{topic} site:producthunt.com` for small tools
- `{topic} deployed real-world` or `{topic} production use`

---

### Round 2 — False-Positive Extraction  *(LLM reasoning step — no API call)*

Read Round 1 results and produce this JSON before proceeding:

```json
{
  "false_positive_patterns": [],
  "true_hit_signals": [],
  "refined_constraint_terms": [],
  "negative_terms": [],
  "paper_repo_candidates": [],
  "independent_repo_candidates": [],
  "product_candidates": [],
  "missing_rings": [],
  "huggingface_relevant": false
}
```

Field guidance:

- `false_positive_patterns`: recurring result types that are clearly not what the user wants
  (e.g. "ESP-IDF documentation", "general embedded tutorials", "unrelated sensor papers")
- `true_hit_signals`: vocabulary, repo names, organization names found in genuine hits
- `refined_constraint_terms`: 1-2 words that distinguish the real target from false positives
- `negative_terms`: words to add as exclusions in Round 3 queries
- `paper_repo_candidates`: repos that appear to be directly linked to research papers
- `independent_repo_candidates`: repos solving the problem independently
- `product_candidates`: commercial or deployed products found so far
- `missing_rings`: which rings had no coverage (e.g. "Ring 1 incomplete — no paper anchors")
- `huggingface_relevant`: whether HuggingFace is a useful source for this topic

---

### Round 3 — Precision Search

Use Round 2 outputs to run targeted queries. Explicitly apply `negative_terms` and
`refined_constraint_terms`.

Query construction rules:

| Target | Query form |
|---|---|
| Paper-linked repo | `"{system_name}" site:github.com` |
| Paper-linked repo | `"{paper_title}" github implementation code` |
| Independent repo | `{problem} {action} {refined_constraint} -"{negative_term}"` |
| GitHub topic | `topic:{tag_1} topic:{tag_2} stars:>100` |
| Awesome list | `awesome {topic_slug} github` |
| HuggingFace | `{topic} huggingface.co/models` or `huggingface.co/spaces` |
| Product | `{problem} {artifact} product OR service OR API` |
| Startup | `{topic} startup OR company site:crunchbase.com` |
| Tech blog | `{topic} {refined_constraint} engineering blog OR technical post` |

For each query, note which ring and which false-positive pattern it is designed to avoid.

---

### Round 4 — Relevance Gate  *(LLM reasoning step — no API call)*

Every candidate result must pass this rubric before entering the final pool.

Questions (all must be yes):

1. Does this result address the actual problem described in the topic, not just share keywords?
   Apply `false_positive_patterns` from Round 2 as explicit exclusion rules.

2. Is this an implementation (code, product, system, deployment) rather than a description
   (documentation, tutorial, academic paper, marketing copy)?

3. Does this result add distinct information relative to other results already in the pool?
   Reject near-duplicates even if both pass the first two questions.

Rejection rules:
- reject if the result matches any `false_positive_patterns` from Round 2
- reject if the result is the documentation or official tutorial for a tool that is itself
  a dependency of what the user is looking for (e.g., ESP-IDF docs when searching for
  tools that automate ESP-IDF)
- reject if the repo has 0 stars and no recent commits and no paper linkage

---

### Round 5 — Depth Extraction

For each result that passed Round 4, extract structured metadata.

**For GitHub repositories:**

```json
{
  "name": "",
  "url": "",
  "ring": 1,
  "stars": 0,
  "last_commit": "",
  "language_stack": [],
  "architecture_summary": "",
  "paper_linked": false,
  "paper_reference": "",
  "deployment_pattern": "",
  "maturity": "prototype | active | production-grade | abandoned",
  "why_relevant": ""
}
```

Maturity heuristics:
- `prototype`: stars < 50, no releases, README only
- `active`: stars > 50, recent commits, some documentation
- `production-grade`: stars > 500, releases, CI, used by other projects
- `abandoned`: no commits in > 18 months

**For products / startups:**

```json
{
  "name": "",
  "url": "",
  "ring": 2,
  "organization": "",
  "year_founded_or_launched": "",
  "funding_stage": "",
  "technical_approach": "",
  "deployment_context": "",
  "why_relevant": ""
}
```

**For news / blog posts / ecosystem signals:**

```json
{
  "title": "",
  "url": "",
  "ring": 3,
  "source": "",
  "date": "",
  "signal_type": "product_launch | funding | deployment | technical_writeup | community",
  "engineering_takeaway": "",
  "why_relevant": ""
}
```

---

### Round 6 — Readiness Assessment  *(LLM reasoning step — no API call)*

After collecting all three rings, synthesize a Technology Readiness assessment:

```
Readiness Level:
  research_only       — papers exist, no implementations found
  early_prototype     — a few research repos, no production use signals
  active_development  — multiple independent implementations, active community
  commercial_traction — products exist, startups funded, or big-tech adoption
  mature_ecosystem    — standard tools exist, widely deployed, large community

Evidence:
  Ring 1 coverage:    {N} paper-linked repos found
  Ring 2 coverage:    {N} independent implementations found
  Ring 3 coverage:    {N} industry/deployment signals found

Gap analysis:
  - What's missing (e.g. "no production-grade library exists yet")
  - What's surprising (e.g. "3 well-funded startups despite limited open-source")
  - Best entry point for an engineer wanting to implement this today
```

---

## HTML Output

Write a single generated page to:
```
output/engineering.html
```

Load the template from:
```
assets/engineering.html
```

If the user requests standalone topic-specific output:
- generate `output/projects/{topic_slug}/engineering.html`
- do not overwrite the shared `output/engineering.html`

Fill:
- `{{TOPIC}}`
- `{{YEAR_RANGE}}`
- `{{LAST_UPDATED}}`
- `{{READINESS_LEVEL}}`
- `{{READINESS_EVIDENCE}}`
- `{{KEY_TAKEAWAY}}`
- `{{GAP_ANALYSIS}}`
- `{{RING1_ITEMS}}`
- `{{RING2_ITEMS}}`
- `{{RING3_ITEMS}}`

The engineering page is separate from `output/kanban.html`.
Paper page stays focused on papers; engineering page stays focused on implementations.
The paper page should link to the engineering page and vice versa.
For bilingual browsing, generated engineering blocks should include both Chinese and English
copies using `.lang-zh` and `.lang-en` wrappers so the page-level language toggle can switch views.

---

## Response Format

```
Engineering Scout — {TOPIC}
Rounds: Decomposition → Discovery → FP Extraction → Precision → Gate → Depth → Readiness

Readiness: {READINESS_LEVEL}

Ring 1 — Paper-Linked:   {N} results
Ring 2 — Independent:    {N} results
Ring 3 — Ecosystem:      {N} results

Key findings:

[Ring 1]
1. {repo/product name} — {stars} ★ — {maturity}
   {why_relevant}

[Ring 2]
2. {repo/product name} — {organization}
   {technical_approach}

[Ring 3]
3. {title} — {source} {date}
   {engineering_takeaway}

Gap analysis:
{gap_analysis}

Best entry point for implementation today:
{one concrete recommendation}

Engineering page: output/engineering.html
```

---

## Error Handling

| Error | Action |
|---|---|
| Ring 1 empty (no paper anchors) | note it explicitly; proceed with Ring 2 and 3 |
| GitHub search returns only documentation | apply false-positive extraction; switch to topic-tag queries |
| No products or startups found | assess as `research_only` or `early_prototype`; do not fabricate products |
| HuggingFace not relevant | skip without comment |
| Marketing-heavy sources | extract only technically defensible claims; mark the rest as unverified |
| Round 4 rejects > 80% of candidates | warn user; report what the actual false-positive pattern is |
| Crunchbase / funding data unavailable | note funding stage as unknown; use other signals |
