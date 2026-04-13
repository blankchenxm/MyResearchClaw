# MyResearchClaw

A Claude Code agent system for searching and tracking academic papers from top venues.

## Skills

### `/conference-scout` — Paper Search

Searches Semantic Scholar, DBLP, and arXiv for papers from top conferences by topic and year range. Results accumulate in a persistent kanban board.

**Usage:**
```
/conference-scout
帮我搜索 wearable audio privacy 在 IoT 顶会 2022-2025 年的论文
```
Trigger phrases: `搜论文`, `find papers`, `顶会论文`, `[topic] papers in [conference]`

### `/paper-reader` — Deep Reading

Deep-reads a single paper and generates structured DNL (Deep Note & List) reading notes. Moves the paper to the "Reading" column in the kanban.

**Usage:** Click **Read Paper** on any kanban card — it shows the command to paste:
```
/paper-reader https://arxiv.org/abs/2401.XXXXX
/paper-reader https://doi.org/10.1145/XXXXXXX
```

---

## Kanban board

| File | Purpose |
|------|---------|
| `output/kanban.html` | Dark-themed 3-column board (To Read / Reading / Done). Open in browser. |
| `output/papers.json` | Persistent data store. Papers accumulate across searches, deduplicated by URL. |
| `output/notes/` | DNL reading notes, one `.md` file per paper. |

Paper status lifecycle: `unread` → `reading` → `done`

---

## Supported venue groups

| Group | Conferences |
|-------|-------------|
| `ai_ml` | NeurIPS, ICLR, ICML, AAAI, CVPR, ACL, EMNLP |
| `iot_systems` | MobiCom, MobiSys, SenSys, UbiComp/IMWUT, IPSN |
| `networking` | SIGCOMM, NSDI, INFOCOM |
| `systems` | OSDI, SOSP, ATC, EuroSys |
| `security` | USENIX Security, CCS, IEEE S&P, NDSS |
| `hci` | CHI, UIST, CSCW |

---

## Version history

### `conference-scout`

#### v0.1 — 2026-04-13 (commit `661cec2`)

Initial release. Basic paper search with chat-only output.

- **Data sources:** Semantic Scholar (primary) + arXiv (supplementary). No DBLP.
- **Venue groups:** 4 groups — `ai_ml`, `iot_systems`, `networking`, `systems`.
- **Output:** Chat text summary only. No persistent storage, no HTML file.
- **Summaries:** English one-sentence contribution summaries only.
- **Error handling:** On Semantic Scholar 429 — wait 2s, retry once, then fall back to arXiv only. No explicit TLS handling.
- **Venue matching:** Case-insensitive substring on `venue` field.

#### v2.0 — 2026-04-13 (commit `82897dc`)

Major rewrite. Persistent kanban system, DBLP fallback, Chinese summaries, two new venue groups.

**New: DBLP fallback (Step 1b)**
- Added DBLP (`dblp.org/search/publ/api`) as an explicit fallback data source between Semantic Scholar and arXiv.
- On SS 429: immediately switch to DBLP, no retry. Run 2–3 DBLP queries with different keyword subsets to maximize coverage.
- DBLP is reliable with no rate limit; fills the gap when SS is rate-limited.

**New: two venue groups**
- Added `security`: USENIX Security, CCS, IEEE S&P, NDSS.
- Added `hci`: CHI, UIST, CSCW.

**New: Chinese summaries**
- Every paper now gets both `summary_en` (English) and `summary_zh` (Chinese), generated from paper content.
- Both are shown as stacked blocks on each kanban card.

**New: persistent JSON + kanban system**
- Replaced per-search static HTML files with a persistent data layer:
  - `output/papers.json` — accumulates all papers across searches, deduplicated by URL. Stores status, notes path, tags, and both summaries.
  - `output/kanban.html` — single file, always overwritten. Three columns: To Read / Reading / Done.
- Paper card HTML template with EN+ZH summaries, View Paper link, Read Paper button.
- Read Paper button shows `/paper-reader {url}` toast popup for user to paste in Claude Code terminal.

**Improved: error handling**
- SS 429 → immediately switch to DBLP (no retry).
- TLS/connection error → retry once, then switch to DBLP.
- arXiv: explicitly use `export.arxiv.org` for API queries (not `arxiv.org`); filter by `<published>` year.

---

### `paper-reader`

#### v1.0 — 2026-04-13 (commit `82897dc`)

Initial release. Deep reading via DNL framework, integrated with kanban.

- **Input:** arXiv URL/ID or DOI/ACM URL. Fetches abstract page + HTML full text (arXiv) or landing page (DOI).
- **DNL 7-section framework:**
  1. Metadata — title, alias, venue, links, rating
  2. Why-read — one-sentence key claim + key observation
  3. CRGP — Context / Related work / Gap / Proposal (from Introduction)
  4. Figures — key figures with arXiv HTML URLs + one-line descriptions
  5. Experiments — main results table, ablation highlights, limitations
  6. Why it matters — 2–4 research insights relevant to your area
  7. Scoring — breakdown of Base + Quality + Observation (max 5/5)
- **Output:** `output/notes/{paper_id}.md` — markdown, git-friendly, Obsidian-compatible.
- **Kanban integration:** Sets paper `status` to `"reading"` in `papers.json`; sets `note_path` to the saved file. Regenerates `kanban.html` — paper moves to Reading column, Notes button appears on the card.
- **Papers not in kanban:** If the paper URL is not in `papers.json`, creates a new entry automatically.

---

## Project structure

```
.claude/
  settings.local.json          # domain permissions for WebFetch
  skills/
    conference-scout/
      SKILL.md                 # v2.0 search skill definition
      templates/kanban.html    # kanban HTML template (dark theme)
    paper-reader/
      SKILL.md                 # v1.0 deep reading skill definition
output/                        # gitignored; generated at runtime
  papers.json                  # persistent paper database
  kanban.html                  # generated kanban board
  notes/                       # DNL reading notes (markdown)
```
