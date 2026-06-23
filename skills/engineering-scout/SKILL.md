---
name: engineering-scout
description: For one research topic, collect implementation evidence (GitHub repos, products, startups, technical posts) organized into three distance rings — paper-linked / independent / industry-ecosystem — and produce a Technology Readiness assessment with concrete gaps. Iterative search with false-positive extraction (e.g. don't return ESP-IDF docs when the user wants tools that automate ESP-IDF). Persist to output/projects/{slug}/engineering.html. Use when the user wants to know whether a topic has open-source implementations, commercial products, or real-world deployment signals; triggers include 工程实现, 开源项目, GitHub 搜索, 有没有产品, 行业动态, find implementations, engineering scout, "how is X implemented in practice". Not for paper search — that's conference-scout.
---

# Engineering Scout

Iterative search agent that turns a research topic into a three-ring implementation map plus a Technology Readiness assessment.

## Inputs

| Field | Required | Default |
|---|---|---|
| `topic` | yes | (or inherit from last conference-scout run) |
| `paper_anchors` | no | inherit system names / authors / arXiv IDs from last conference-scout run |
| `year_start` | no | auto-inferred |
| `year_end` | no | current year |
| `focus` | no | `all`; can be `github` / `products` / `news` |

If `conference-scout` just ran on the same topic, inherit `topic` and `paper_anchors` automatically — don't ask.

## Three rings

Search them in order, don't jump to Ring 3 before Ring 1+2 are reasonably covered.

| Ring | What | Quality signal |
|---|---|---|
| 1. Paper-linked | repos / artifacts directly produced by papers on this topic | paper authorship filters quality |
| 2. Independent | GitHub projects / products solving the same problem independently | assess maturity, adoption, architecture |
| 3. Ecosystem | news, startups, technical blogs, community, product launches | where the field sits on the research-to-deployment spectrum |

## Query decomposition (do this before any search)

Decompose the topic into three dimensions, write them down, then build queries from combinations:

```
problem:   what is being solved          (noun phrase describing the challenge)
action:    operation being performed     (verb phrase: automated / orchestrated / CI/CD / OTA)
artifact:  what the solution produces    (tool / framework / pipeline / system)
```

**Example** — topic `自动烧入PCB固件`:

```
problem:   firmware flashing for embedded devices
action:    automated / CI/CD / orchestrated / batch / OTA
artifact:  tool / pipeline / framework / workflow

queries:
  - "firmware flashing automation tool" github
  - "automated firmware deployment pipeline embedded"
  - "OTA firmware CI/CD embedded systems"
  - firmware flash orchestration stars:>50
  - "auto flash" embedded microcontroller site:github.com
```

This split is the **primary defense against false positives** like ESP-IDF docs when the user wants tools that automate ESP-IDF.

## Workflow

6 rounds. Log which round. Don't skip. Don't emit final results before Round 4.

### Round 1 — Broad Discovery

**Ring 1 (paper-linked)** — if `paper_anchors` exist:
- `"{system_name}" github` — one per system name
- `"{paper_title}" implementation` — top 2-3 papers
- `"{author_name}" {topic} code`
- `site:github.com {arXiv_id}` — if arXiv IDs known

If no anchors, skip Ring 1 for now and note it as missing.

**Ring 2 (independent)** — 3-4 queries from the `problem + action + artifact` decomposition. Don't run all permutations.

**GitHub tactics:**
- Topic tags: `topic:{relevant-tag}` (e.g. `topic:firmware-update topic:ota`) — author-labeled, much more precise than keyword search
- Stars filter: `stars:>50 pushed:>{year}-01-01` to exclude abandoned
- Awesome lists: `awesome-{topic}` — curated lists exist for most active subfields
- HuggingFace: for AI/ML topics, search `huggingface.co/models` and `huggingface.co/spaces`

**Ring 3 (ecosystem):**
- `{topic} startup funding`
- `{topic} product launch site:techcrunch.com OR site:venturebeat.com`
- `{topic} blog post technical implementation`
- `{topic} site:producthunt.com`
- `{topic} deployed real-world` / `{topic} production use`

### Round 2 — False-Positive Extraction *(LLM only, no API)*

Produce this JSON before Round 3:

```json
{
  "false_positive_patterns": [],     // recurring NON-target result types (e.g. "ESP-IDF documentation", "general embedded tutorials")
  "true_hit_signals": [],            // vocabulary / repo names / orgs found in genuine hits
  "refined_constraint_terms": [],    // 1-2 words distinguishing real targets from FPs
  "negative_terms": [],              // exclusions for Round 3 queries
  "paper_repo_candidates": [],
  "independent_repo_candidates": [],
  "product_candidates": [],
  "missing_rings": [],               // e.g. "Ring 1 incomplete — no paper anchors"
  "huggingface_relevant": false
}
```

### Round 3 — Precision Search

Apply `negative_terms` and `refined_constraint_terms` explicitly. Query forms:

| Target | Query |
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

For each query note: which ring, which FP pattern it's designed to avoid.

### Round 4 — Relevance Gate *(LLM only, no API)*

Every candidate must pass all three:

1. Addresses the **actual problem** (not just shares keywords)? Apply `false_positive_patterns` as exclusion rules.
2. Is an **implementation** (code / product / system / deployment), not a description (docs / tutorial / academic paper / marketing)?
3. Adds **distinct information** vs. results already in the pool (reject near-duplicates).

Hard rejects:
- matches any `false_positive_patterns` from Round 2
- is documentation / official tutorial for a tool that is itself a *dependency* of what the user wants
- 0 stars + no recent commits + no paper linkage

### Round 5 — Depth Extraction

For each Round-4 survivor, extract structured metadata. Three schemas:

**GitHub repository:**
```json
{
  "name": "", "url": "", "ring": 1, "stars": 0, "last_commit": "",
  "language_stack": [], "architecture_summary": "",
  "paper_linked": false, "paper_reference": "",
  "deployment_pattern": "",
  "maturity": "prototype | active | production-grade | abandoned",
  "why_relevant": ""
}
```

Maturity heuristics:
- `prototype`: < 50 stars, no releases, README only
- `active`: > 50 stars, recent commits, some docs
- `production-grade`: > 500 stars, releases, CI, used by other projects
- `abandoned`: no commits in > 18 months

**Product / startup:**
```json
{
  "name": "", "url": "", "ring": 2, "organization": "",
  "year_founded_or_launched": "", "funding_stage": "",
  "technical_approach": "", "deployment_context": "",
  "why_relevant": ""
}
```

**News / blog / ecosystem:**
```json
{
  "title": "", "url": "", "ring": 3, "source": "", "date": "",
  "signal_type": "product_launch | funding | deployment | technical_writeup | community",
  "engineering_takeaway": "", "why_relevant": ""
}
```

### Round 6 — Readiness Assessment *(LLM only, no API)*

Synthesize a Technology Readiness assessment:

```
Readiness Level (pick one):
  research_only       — papers exist, no implementations
  early_prototype     — a few research repos, no production signals
  active_development  — multiple independent implementations, active community
  commercial_traction — products exist / startups funded / big-tech adoption
  mature_ecosystem    — standard tools, widely deployed, large community

Evidence:
  Ring 1: {N} paper-linked
  Ring 2: {N} independent
  Ring 3: {N} ecosystem signals

Gap analysis:
  - What's missing                  (e.g. "no production-grade library exists yet")
  - What's surprising               (e.g. "3 well-funded startups despite limited OSS")
  - Best entry point for an engineer wanting to implement this today
```

## Output

Generate `output/projects/{topic_slug}/engineering.html` from `assets/engineering.html`. Do NOT overwrite shared `output/engineering.html`.

Template placeholders (the layout handles them — just write the data):
`{{TOPIC}}`, `{{YEAR_RANGE}}`, `{{LAST_UPDATED}}`, `{{READINESS_LEVEL}}`, `{{READINESS_EVIDENCE}}`, `{{KEY_TAKEAWAY}}`, `{{GAP_ANALYSIS}}`, `{{RING1_ITEMS}}`, `{{RING2_ITEMS}}`, `{{RING3_ITEMS}}`.

Each rendered item: include both Chinese and English copies wrapped in `.lang-zh` / `.lang-en` so the page-level language toggle works.

Cross-link to the paper page; paper page should also link back.

## Response

```
Engineering Scout — {TOPIC}
Rounds: Decomposition → Discovery → FP Extraction → Precision → Gate → Depth → Readiness

Readiness: {READINESS_LEVEL}

Ring 1 — Paper-Linked:  {N}
Ring 2 — Independent:   {N}
Ring 3 — Ecosystem:     {N}

Key findings:

[Ring 1]
1. {name} — {stars}★ — {maturity}
   {why_relevant}

[Ring 2]
2. {name} — {organization}
   {technical_approach}

[Ring 3]
3. {title} — {source} {date}
   {engineering_takeaway}

Gap analysis:
{gap_analysis}

Best entry point today: {one concrete recommendation}

Page: output/projects/{topic_slug}/engineering.html
```

## Failure signals

| 信号 | 含义 | 方向调整 |
|---|---|---|
| Ring 1 empty (no paper_anchors) | conference-scout 没跑过 / 该领域无 paper-linked 实现 | 标记缺失，继续 Ring 2/3，不要伪造 |
| GitHub 搜索只返回 documentation | query 命中了 tool 本身而不是 tool 的用户 | Round 2 提 FP patterns，Round 3 用 topic-tag |
| 找不到 products / startups | 还没到 commercial_traction | 评估为 `research_only` 或 `early_prototype`，不要编造 |
| HuggingFace 不相关 | 该 topic 不在 ML/AI 范畴 | 跳过，不要解释 |
| Marketing-heavy 来源 | startup / vendor 自吹 | 只抽取 technically defensible 的部分，其余标 unverified |
| Round 4 拒绝 > 80% | query 太宽或 FP patterns 漏写 | 暂停告知用户；报具体的 FP pattern；放宽一个条件 |
| Crunchbase 不可访问 | 数据源失败 | funding_stage 标 unknown，用其他信号兜底 |
