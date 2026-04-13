---
name: conference-scout
description: >
  Search for top-conference academic papers by topic, year range, and venue type (AI/ML, IoT, networking, systems).
  TRIGGER when user asks to find/search papers, mentions specific conferences (NeurIPS/ICLR/ICML/MobiCom etc.),
  or uses phrases like: 搜论文, find papers, 顶会论文, paper search, scout papers, conference papers,
  "[topic] papers in [conference]", "[topic]领域近[N]年顶会论文".
---

# Conference Scout — Top-Venue Paper Search

**Goal:** Given a topic + year range + conference group(s), return the most relevant and highly-cited papers from target top venues.

**Data sources:**
- **Semantic Scholar API** — primary, for venue-filtered results + citation counts
- **arXiv Atom/XML API** — supplementary, for recent related preprints (especially useful when conference proceedings are not yet indexed)

---

## ⚙️ Step 0 — Parse User Input

Extract from the user's message:

| Field | Description | Example |
|---|---|---|
| `topic` | Research topic | "federated learning", "LLM reasoning" |
| `year_start` | Start year of range | 2022 |
| `year_end` | End year (default: current year) | 2025 |
| `conference_groups` | Which venue group(s) to search | `["ai_ml"]`, `["iot_systems", "networking"]` |
| `specific_venues` | Optional: user-specified venues directly | `["NeurIPS", "MobiCom"]` |

**Conference group → venue name mapping** (use this to build venue aliases for matching):

```yaml
ai_ml:
  - name: NeurIPS
    aliases: ["NeurIPS", "Neural Information Processing Systems", "NIPS"]
  - name: ICLR
    aliases: ["ICLR", "International Conference on Learning Representations"]
  - name: ICML
    aliases: ["ICML", "International Conference on Machine Learning"]
  - name: AAAI
    aliases: ["AAAI"]
  - name: CVPR
    aliases: ["CVPR", "Computer Vision and Pattern Recognition"]
  - name: ACL
    aliases: ["ACL", "Association for Computational Linguistics"]
  - name: EMNLP
    aliases: ["EMNLP"]

iot_systems:
  - name: MobiCom
    aliases: ["MobiCom", "Mobile Computing and Networking"]
  - name: MobiSys
    aliases: ["MobiSys", "Mobile Systems"]
  - name: SenSys
    aliases: ["SenSys", "Embedded Networked Sensor Systems"]
  - name: UbiComp
    aliases: ["UbiComp", "Pervasive and Ubiquitous Computing"]
  - name: IPSN
    aliases: ["IPSN"]

networking:
  - name: SIGCOMM
    aliases: ["SIGCOMM"]
  - name: NSDI
    aliases: ["NSDI", "Networked Systems Design"]
  - name: INFOCOM
    aliases: ["INFOCOM"]

systems:
  - name: OSDI
    aliases: ["OSDI", "Operating Systems Design"]
  - name: SOSP
    aliases: ["SOSP", "Operating Systems Principles"]
  - name: ATC
    aliases: ["ATC", "USENIX Annual Technical"]
  - name: EuroSys
    aliases: ["EuroSys"]
```

If `conference_groups` not specified, ask the user: "你想搜哪类顶会？AI/ML、IoT、网络、还是系统？"

---

## 📡 Step 1 — Semantic Scholar Search (Primary)

**API endpoint:**
```
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={TOPIC}
  &fields=title,authors,year,venue,abstract,citationCount,externalIds,url
  &limit=50
  &year={YEAR_START}-{YEAR_END}
```

- Replace spaces in `TOPIC` with `+`
- Set `YEAR_START` and `YEAR_END` from Step 0
- Run **1–2 queries** with slightly different phrasings if the first returns fewer than 10 results
  - Primary: exact topic phrase, e.g., `"federated+learning"`
  - Fallback: split into keywords, e.g., `federated+learning+privacy`

**Rate limit (429) handling:**
- If 429 received: wait 3 seconds, retry once with a slightly different query (add/remove one keyword)
- If still 429: skip Semantic Scholar entirely, proceed with arXiv only, note it in output
- To avoid 429: do not run more than 2 SS queries per skill execution

**Parse response JSON:**
```json
{
  "data": [
    {
      "paperId": "...",
      "title": "...",
      "year": 2024,
      "venue": "NeurIPS",
      "authors": [{"name": "..."}],
      "abstract": "...",
      "citationCount": 142,
      "externalIds": {"ArXiv": "2401.XXXXX"},
      "url": "https://www.semanticscholar.org/paper/..."
    }
  ]
}
```

**Venue filter (local, after fetch):**
- For each paper, check if `venue` field contains ANY alias from the target venue list
- Match is case-insensitive substring: `paper.venue.lower().includes(alias.lower())`
- Keep only papers that match at least one target venue

**Build result list** with fields: `title`, `authors`, `year`, `venue`, `abstract`, `citationCount`, `arxivId` (from `externalIds.ArXiv` if present), `url`

---

## 🔬 Step 2 — arXiv Supplementary Search

Use arXiv to find **recent related preprints** that may not yet appear in conference proceedings (e.g., workshop papers, arxiv-first papers from target authors).

**API endpoint:**
```
GET http://export.arxiv.org/api/query
  ?search_query=all:{TOPIC}
  &sortBy=submittedDate
  &sortOrder=descending
  &max_results=20
  &start=0
```

- Filter: only keep papers with `<published>` date within `[YEAR_START, YEAR_END]`
- Parse XML Atom response fields: `<title>`, `<author>`, `<summary>`, `<published>`, `<id>` (arXiv URL)

**Selection criteria for arXiv results** (more selective than SS, since no venue filter):
- Title or abstract must contain at least 2 words from the topic
- Must be from `YEAR_START` or later
- Prefer papers that mention target venues in their abstract (e.g., "presented at NeurIPS", "accepted to ICML")

Collect up to **5 arXiv papers** as supplementary results. Label them clearly as `[arXiv — not yet confirmed in venue]`.

---

## 🏆 Step 3 — Merge & Rank

**Deduplication:** If an arXiv paper has the same title as a Semantic Scholar result, keep only the SS version (has citation count).

**Scoring** (sort descending):

| Signal | Score |
|---|---|
| citationCount ≥ 100 | +3 |
| citationCount 50–99 | +2 |
| citationCount 10–49 | +1 |
| citationCount < 10 | +0 |
| Venue is in target group (confirmed) | +2 |
| Title contains exact topic phrase | +1.5 |
| Abstract contains ≥ 3 topic keywords | +1 |
| Paper year = most recent year in range | +0.5 |
| arXiv only (unconfirmed venue) | −1 |

Sort by score descending. Output:
- **Top 8** from Semantic Scholar (venue-confirmed)
- **Top 3** from arXiv (supplementary)

---

## 🌐 Step 4 — Generate HTML Dashboard

**Template location:** Find `results.html` in the same directory as this SKILL.md file, under `templates/results.html`.

1. Load the template with `read`
2. Build the full HTML by replacing placeholders and expanding paper card blocks:

**Header placeholders:**

| Placeholder | Value |
|---|---|
| `{{TOPIC}}` | The topic string |
| `{{YEAR_START}}` | Start year |
| `{{YEAR_END}}` | End year |
| `{{VENUES}}` | Comma-separated venue names searched |
| `{{TOTAL_CONFIRMED}}` | Count of venue-confirmed papers |
| `{{TOTAL_ARXIV}}` | Count of arXiv papers |
| `{{DATE}}` | Today's date |

**Paper card blocks:**
- The template contains a single example card between `<!-- CONFIRMED_PAPERS_START -->` and `<!-- CONFIRMED_PAPERS_END -->` comments
- Replace the block with **one card per confirmed paper**, repeating the `<div class="paper-card confirmed">` block for each paper
- Similarly replace the arXiv block between `<!-- ARXIV_PAPERS_START -->` and `<!-- ARXIV_PAPERS_END -->`

**Per-paper placeholders:**

| Placeholder | Value |
|---|---|
| `{{RANK}}` | 1, 2, 3... |
| `{{TITLE}}` | Paper title |
| `{{URL}}` | Paper URL (SS link or arXiv link) |
| `{{VENUE}}` | Venue name |
| `{{YEAR}}` | Publication year |
| `{{CITATIONS}}` | Citation count |
| `{{AUTHORS}}` | First author + et al. |
| `{{SUMMARY}}` | One-sentence contribution summary |
| `{{ARXIV_TITLE}}`, `{{ARXIV_URL}}`, `{{ARXIV_YEAR}}`, `{{ARXIV_AUTHORS}}`, `{{ARXIV_SUMMARY}}` | Same for arXiv papers |

3. Save output to `~/MyResearchClaw-output/{TOPIC_SLUG}-{DATE}.html`
   - `TOPIC_SLUG` = topic with spaces replaced by `-`, lowercased
   - Example: `~/MyResearchClaw-output/federated-learning-2026-04-10.html`
4. Report: `🌐 HTML dashboard saved → ~/MyResearchClaw-output/{filename}`

**Never leave unfilled `{{PLACEHOLDER}}` tags in the output HTML.**

---

## 📋 Step 5 — Chat Summary Output

After generating HTML, output a compact chat summary:

```
📡 Conference Scout — {TOPIC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {YEAR_START}–{YEAR_END}  |  🏛️ {Venues searched}

── Venue-Confirmed ({TOTAL_CONFIRMED}) ──────────────

1️⃣ {Title}
   👤 {First Author} et al. | 📍 {Venue} {Year} | ★ {citationCount}
   💡 {One-sentence summary}
   🔗 {URL}

2️⃣ ... (up to 8)

── arXiv Supplements ({TOTAL_ARXIV}) ────────────

🗂️ {Title}
   👤 {Author} | 📅 {Year} | [venue unconfirmed]
   🔗 {arXiv URL}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 Full dashboard → ~/MyResearchClaw-output/{filename}
```

If fewer than 3 venue-confirmed papers found:
> ⚠️ 在指定顶会中匹配结果较少（{N}篇）。可能原因：该主题在这些会议中覆盖有限，或 Semantic Scholar venue 字段未标准化。已扩展显示 arXiv 相关论文。

---

## ⚠️ Error Handling

| Error | Handling |
|---|---|
| Semantic Scholar returns 429 (rate limit) | Wait 2s, retry once; if still blocked, proceed with arXiv only and note it |
| Semantic Scholar returns empty data | Broaden query (split phrase into individual keywords), retry once |
| arXiv API returns empty | Note "arXiv temporarily unavailable", continue with SS results only |
| No papers match venue filter | Show top 5 SS results unfiltered, flag with ⚠️ "venue filter yielded no results — showing best topic matches instead" |
| year_end not specified | Default to current year (2026) |
| Topic is ambiguous or too broad | Ask user: "你的主题比较宽泛，能再具体一点吗？比如加上方法名或应用场景" |
