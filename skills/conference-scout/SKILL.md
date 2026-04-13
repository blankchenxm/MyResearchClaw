---
name: conference-scout
description: >
  Search top-conference papers by topic, time range, and venue type.
  Use when user says: 搜论文, find papers, conference papers, 顶会论文, paper search, scout papers.
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

## 📋 Step 4 — Format Output

```
📡 Conference Paper Scout Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Topic: {TOPIC}
📅 Range: {YEAR_START}–{YEAR_END}
🏛️ Venues: {comma-separated venue names searched}

── Top Papers (Venue-Confirmed) ──────────────

1️⃣ {Title}
   👤 {First Author} et al. | 📍 {Venue} {Year} | 🌟 {citationCount} citations
   💡 {One-sentence summary of contribution}
   🔗 {URL or https://arxiv.org/abs/{arxivId} if available}

2️⃣ {Title}
   ... (repeat for up to 8 papers)

── Supplementary (arXiv) ─────────────────────

🗂️ {Title}  [arXiv — venue unconfirmed]
   👤 {Author} et al. | 📅 {Year}
   💡 {One-sentence summary}
   🔗 https://arxiv.org/abs/{arxivId}

... (up to 3 arXiv papers)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 想深读某篇？给我链接说 "帮我读一下"
💬 Want different venues? Tell me which group: ai_ml / iot_systems / networking / systems
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
