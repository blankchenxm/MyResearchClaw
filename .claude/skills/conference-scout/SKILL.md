---
name: conference-scout
description: >
  Search for top-conference academic papers by topic, year range, and venue type (AI/ML, IoT, networking, systems).
  TRIGGER when user asks to find/search papers, mentions specific conferences (NeurIPS/ICLR/ICML/MobiCom etc.),
  or uses phrases like: 搜论文, find papers, 顶会论文, paper search, scout papers, conference papers,
  "[topic] papers in [conference]", "[topic]领域近[N]年顶会论文".
---

# Conference Scout — Top-Venue Paper Search (v2.0)

**Goal:** Find top-conference papers on a given topic, add them to the persistent kanban board, and regenerate `output/kanban.html`.

**Data sources (in priority order):**
1. **Semantic Scholar API** — primary; venue-filtered results with citation counts
2. **DBLP API** — fallback when SS is rate-limited; reliable, no rate limit
3. **arXiv Atom/XML API** — supplementary; recent preprints not yet in proceedings

**Output:** Update `output/papers.json` → regenerate `output/kanban.html`

---

## ⚙️ Step 0 — Parse User Input

Extract:

| Field | Description | Default |
|---|---|---|
| `topic` | Research topic (English preferred) | required |
| `year_start` | Start year | 2022 |
| `year_end` | End year | current year |
| `conference_groups` | Venue group(s) | ask if missing |
| `specific_venues` | Override venue list | optional |

**Conference group → venue aliases:**

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
  - UbiComp / Pervasive and Ubiquitous Computing / IMWUT / Interactive Mobile Wearable and Ubiquitous Technologies
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

If `conference_groups` not specified: ask "你想搜哪类顶会？AI/ML、IoT、安全、HCI、网络还是系统？"

---

## 📡 Step 1 — Semantic Scholar Search (Primary)

**Endpoint:**
```
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={TOPIC_KEYWORDS}
  &fields=title,authors,year,venue,abstract,citationCount,externalIds,url
  &limit=50
  &year={YEAR_START}-{YEAR_END}
```

**Rate limit & network error handling (CRITICAL):**

| Error | Action |
|---|---|
| HTTP 429 | Do NOT retry immediately. Mark SS as unavailable, proceed to DBLP fallback (Step 1b) |
| TLS / connection reset | Retry ONCE with identical URL after a brief pause. If fails again, proceed to DBLP |
| Empty `data` array | Try one alternative query (drop one keyword), then proceed to DBLP if still empty |
| HTTP 403 / 401 | Skip SS entirely, proceed to DBLP |

**Run at most 2 SS queries total** (to avoid triggering 429).

**Venue filter (local, post-fetch):** `paper.venue.toLowerCase().includes(alias.toLowerCase())`

---

## 📚 Step 1b — DBLP Fallback (when SS fails or returns < 5 results)

DBLP is reliable, fast, and has no rate limits. Use it as the primary fallback.

**Endpoint:**
```
GET https://dblp.org/search/publ/api?q={QUERY_TERMS}&format=json&h=30&f=0
```

**Query strategy:**
- Use 2–3 of the most distinctive keywords from the topic (DBLP searches paper titles)
- Run 2–3 queries with different keyword subsets to maximize coverage
- Example queries for "wearable AI audio recording": 
  - `audio+sensing+wearable`
  - `audio+privacy+mobile`
  - `wearable+speech+sensing`

**Parse JSON response:**
```json
{
  "result": {
    "hits": {
      "hit": [
        {
          "info": {
            "title": "...",
            "authors": {"author": [{"text": "..."}]},
            "year": "2024",
            "venue": "...",
            "url": "..."
          }
        }
      ]
    }
  }
}
```

**Venue filter:** Same alias matching as SS. Only keep papers from target venues.

**Limitation:** DBLP results lack abstracts and citation counts. For papers found via DBLP:
- `citationCount` = "—"
- `abstract` = fetch from SS by DOI if available, otherwise omit

---

## 🔬 Step 2 — arXiv Supplementary Search

**Endpoint (always use `export.arxiv.org`, NOT `arxiv.org`):**
```
GET http://export.arxiv.org/api/query
  ?search_query=all:{TOPIC_KEYWORDS}
  &sortBy=submittedDate
  &sortOrder=descending
  &max_results=20
  &start=0
```

**Important:** The arXiv export API (`export.arxiv.org`) is always accessible. Do NOT use `arxiv.org` for API queries — use it only for fetching individual paper abstract pages.

**Filter criteria:**
- Paper `<published>` date must be within `[YEAR_START, YEAR_END]` (check the year from the date string)
- Title or abstract must contain ≥ 2 topic keywords
- Prefer papers mentioning target venues in abstract

Collect up to **5 arXiv papers** as supplements.

---

## 🏆 Step 3 — Merge & Rank

**Deduplication:** If a paper appears in both SS and arXiv (same title), keep SS version.

**Scoring:**

| Signal | Score |
|---|---|
| citationCount ≥ 100 | +3 |
| citationCount 50–99 | +2 |
| citationCount 10–49 | +1 |
| Venue confirmed in target group | +2 |
| Title contains exact topic phrase | +1.5 |
| Abstract contains ≥ 3 topic keywords | +1 |
| Year = most recent year in range | +0.5 |
| arXiv only (unconfirmed) | −1 |

Output: **Top 8** venue-confirmed + **Top 3** arXiv supplements.

---

## 🌐 Step 4 — Generate English + Chinese Summaries

For **each paper** (confirmed and arXiv), generate:

1. **`summary_en`** — 1–2 sentence English contribution summary covering: what problem, what approach, key result
2. **`summary_zh`** — 1–2 sentence Chinese summary of the same content (技术要点+核心贡献，面向中文读者)

Keep both summaries concise (~100 words max each).

---

## 💾 Step 5 — Update papers.json + Regenerate kanban.html

### 5a. Load papers.json

Load `output/papers.json` from the project root. If it doesn't exist, create it:

```json
{
  "last_updated": "{TODAY}",
  "searches": [],
  "papers": []
}
```

### 5b. Add new papers (deduplicate)

For each paper in the ranked results:
- Check if a paper with the same `url` already exists in `papers`
- If **not present**: add as new entry with `status: "unread"`
- If **already present**: skip (do not overwrite status or notes)

**Paper object schema:**
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
  "topic": "{TOPIC}",
  "date_added": "{TODAY}",
  "tags": [],
  "note_path": null
}
```

- `id`: lowercase slug from title (first 5 words, spaces→dashes) + `_` + year
- `tags`: auto-derive 2–3 tags from venue and topic keywords

### 5c. Record this search

Append to `searches` array:
```json
{
  "date": "{TODAY}",
  "topic": "{TOPIC}",
  "year_range": "{YEAR_START}-{YEAR_END}",
  "venues": "{COMMA_SEPARATED_VENUES}",
  "papers_added": N
}
```

### 5d. Save papers.json

Write updated JSON back to `output/papers.json`.

### 5e. Regenerate kanban.html

Load template from `templates/kanban.html` (same directory as this SKILL.md).

**Compute template values:**

| Placeholder | Value |
|---|---|
| `{{LAST_UPDATED}}` | today's date |
| `{{TOTAL_PAPERS}}` | len(papers) |
| `{{UNREAD_COUNT}}` | count where status=="unread" |
| `{{READING_COUNT}}` | count where status=="reading" |
| `{{DONE_COUNT}}` | count where status=="done" |
| `{{SEARCH_COUNT}}` | len(searches) |
| `{{SEARCH_TAGS}}` | last 5 searches as `<span class="search-tag">` elements |
| `{{UNREAD_PAPERS}}` | HTML cards for unread papers |
| `{{READING_PAPERS}}` | HTML cards for reading papers |
| `{{DONE_PAPERS}}` | HTML cards for done papers |
| `{{UNREAD_EMPTY}}` | if 0 unread: `<div class="empty-state"><div class="empty-icon">📥</div>No papers queued</div>` else empty string |
| `{{READING_EMPTY}}` | same pattern for reading |
| `{{DONE_EMPTY}}` | same pattern for done |

**Paper card HTML block** (repeat for each paper in the group):

```html
<div class="paper-card {{CARD_CLASS}}">
  <div class="card-header">
    <div class="card-title"><a href="{{URL}}" target="_blank">{{TITLE}}</a></div>
    <span class="citations {{CITE_CLASS}}">★ {{CITATIONS}}</span>
  </div>
  <div class="card-authors">{{AUTHORS}}</div>
  <div class="card-meta">
    <span class="venue-badge {{ARXIV_CLASS}}">{{VENUE}} {{YEAR}}</span>
    {{TAG_SPANS}}
  </div>
  <div class="summary-block">
    <div class="summary-label">EN</div>
    <div class="summary-en">{{SUMMARY_EN}}</div>
    <div class="summary-label" style="margin-top:6px;">中文</div>
    <div class="summary-zh">{{SUMMARY_ZH}}</div>
  </div>
  <div class="card-actions">
    <a href="{{URL}}" target="_blank" class="btn btn-view">🔗 View Paper</a>
    <button class="btn btn-read" onclick="readPaper('{{URL}}', '{{TITLE_ESCAPED}}')">📖 Read Paper</button>
    {{NOTE_BTN}}
  </div>
  {{NOTE_LINK}}
</div>
```

**Placeholder mapping:**
- `{{CARD_CLASS}}`: `is-arxiv` if `is_arxiv` else `is-confirmed`
- `{{CITE_CLASS}}`: `cite-high` (≥50), `cite-mid` (10-49), `cite-low` (1-9), `cite-none` (0 or "—")
- `{{CITATIONS}}`: citation count or "—"
- `{{ARXIV_CLASS}}`: `arxiv` if `is_arxiv` else empty
- `{{TAG_SPANS}}`: up to 3 tags as `<span class="card-tag tag-cyan">tag</span>` (cycle: cyan→purple→pink)
- `{{NOTE_BTN}}`: if `note_path` not null: `<a href="{{NOTE_PATH}}" class="btn btn-done">📄 Notes</a>` else empty
- `{{NOTE_LINK}}`: if `note_path` not null: `<a href="{{NOTE_PATH}}" class="note-link">📝 Reading notes →</a>` else empty
- `{{TITLE_ESCAPED}}`: title with single quotes escaped as `&#39;`

Save to `output/kanban.html` (always the **same file**, overwrite each time).

---

## 📋 Step 6 — Chat Summary Output

```
📡 Conference Scout — {TOPIC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {YEAR_START}–{YEAR_END}  |  🏛️ {Venues}
➕ {N} new papers added  |  📚 {TOTAL} total in kanban

── Venue-Confirmed ({TOTAL_CONFIRMED}) ──────────

1️⃣ {Title}
   👤 {First Author} et al. | 📍 {Venue} {Year} | ★ {citations}
   💡 {summary_en}
   🔗 {URL}

[up to 8]

── arXiv ({TOTAL_ARXIV}) ────────────────────────

🗂️ {Title} | {Year} | [unconfirmed]
   🔗 {arXiv URL}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 Kanban → output/kanban.html
```

---

## ⚠️ Error Handling

| Error | Handling |
|---|---|
| SS 429 | Immediately switch to DBLP; note "SS rate-limited, using DBLP" |
| SS TLS error | Retry once; if still fails, switch to DBLP |
| DBLP returns 0 hits | Try 2 alternative keyword subsets before giving up |
| arXiv returns off-topic results | Filter strictly (both title AND abstract must match) |
| No venue-confirmed papers | Show top 5 unfiltered + ⚠️ warning |
| papers.json malformed | Recreate from scratch; log warning |
| year_end not specified | Default to current year |

---

## 🧪 Test Prompt

To verify the skill is working after setup:

> 帮我搜索联邦学习在AI顶会（NeurIPS/ICLR/ICML）2023-2024年的论文

Expected behavior:
1. Query SS API → if 429, immediately try DBLP
2. arXiv supplementary search via `export.arxiv.org`
3. Papers ranked and deduplicated
4. Chinese + English summaries generated
5. `output/papers.json` updated
6. `output/kanban.html` regenerated
7. Chat summary output
