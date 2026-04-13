---
name: paper-reader
description: >
  Deep-read a paper (arXiv or DOI) and generate structured DNL reading notes.
  Updates papers.json status to "reading" and regenerates kanban.html.
  TRIGGER when user runs /paper-reader {url}, or pastes an arXiv/DOI link with reading intent.
  Phrases: 帮我读, 精读, DNL, paper notes, /paper-reader
---

# Paper Reader — Deep DNL Notes (v1.0)

**Goal:** Fetch and analyze a paper, write structured DNL notes to `output/notes/`, update `output/papers.json`, regenerate `output/kanban.html`.

---

## ⚙️ Step 0 — Parse Input

Extract the paper URL/ID from the input. Supported formats:
- `https://arxiv.org/abs/XXXX.XXXXX`
- `https://arxiv.org/pdf/XXXX.XXXXX`
- `https://doi.org/...` or `https://dl.acm.org/doi/...`
- Bare arXiv ID: `XXXX.XXXXX`

Determine paper type:
- **arXiv**: has `arxiv.org` in URL or bare ID pattern `\d{4}\.\d{4,5}`
- **DOI/ACM/other**: everything else

---

## 📡 Step 1 — Fetch Paper Metadata & Content

### 1a. arXiv papers

Fetch abstract page:
```
GET https://arxiv.org/abs/{ARXIV_ID}
```
Extract: title, authors, abstract, subject categories, submission date.

Then fetch HTML version for full text + figures:
```
GET https://arxiv.org/html/{ARXIV_ID}v1
```
If HTML unavailable (404), use abstract only and note `[HTML version unavailable — using abstract only]`.

### 1b. DOI / ACM / other papers

Fetch the DOI landing page or ACM DL page:
```
GET {URL}
```
Extract: title, authors, abstract, venue, year.

Also try Semantic Scholar for metadata:
```
GET https://api.semanticscholar.org/graph/v1/paper/search?query={TITLE_KEYWORDS}&fields=title,authors,year,venue,abstract,citationCount,externalIds
```

**Note:** For non-arXiv papers, full text may be unavailable. Use abstract + any accessible content. Note limitations clearly in the DNL.

---

## 🔍 Step 2 — Match Paper in papers.json

Load `output/papers.json`.

Find the paper by matching `url` field (or arXiv ID in `arxiv_id` field).

If found:
- Record `paper_id` = the paper's `id` field
- Record `paper_title` for use in filename

If not found:
- Generate a slug: lowercase first 5 words of title, spaces→dashes, append `_` + year
- This paper will be added to papers.json at Step 5

---

## 🧠 Step 3 — Analyze Paper Using DNL Framework

Extract structured content using the **DNL 7-section framework**:

| Section | Content to extract |
|---------|-------------------|
| 0) Metadata | Title, alias, authors, venue, year, links, tags, rating |
| 1) Why-read | One-sentence key claim + key observation |
| 2) CRGP | Context, Related work, Gap, Proposal (from Introduction) |
| 3) Figures | Key figures with URLs from arXiv HTML + one-line descriptions |
| 4) Experiments | Main results table, ablation highlights, limitations |
| 5) Why it matters | Research insights relevant to AI recording / wearable sensing |
| 6) Next steps | Actionable follow-up checkboxes |
| 7) Scoring | Rating breakdown (see below) |

### Scoring System

**Base score:** 1 (any complete paper with benchmarks)

**Quality bonus (0–2):**
- +1: Solid experiments with proper ablation
- +2: Strong ablation + SOTA results + novel methodology

**Observation bonus (0–2):**
- +1: Finding directly relevant to wearable audio / AI recording devices research
- +2: Paradigm-shifting insight for the field

**Final = Base + Quality + Observation** (max 5/5)

### Alias

Generate a short memorable alias (1–2 words) from the paper title, e.g., "Kirigami", "SAMoSA", "WearSE".

---

## 💾 Step 4 — Write DNL Markdown Note

**Output path:** `output/notes/{paper_id}.md`

**Filename example:** `output/notes/kirigami-lightweight-speech-filtering_2024.md`

```markdown
# DNL Deep Note — {ALIAS}

## 0) Metadata
- **Title:** {FULL_TITLE}
- **Alias:** {ALIAS}
- **Authors / Org:** {AUTHORS}
- **Venue / Status:** {VENUE} ({YEAR})
- **Links:**
  - Paper: {URL}
  - HTML: https://arxiv.org/html/{ARXIV_ID}v1  (if arXiv)
  - PDF: https://arxiv.org/pdf/{ARXIV_ID}  (if arXiv)
- **Tags:** {comma-separated tags from papers.json or auto-derived}
- **My rating:** {STARS} ({N}/5)
- **Read depth:** deep
- **Scoring ({BASE}+{QUALITY}+{OBSERVATION}):** {EXPLANATION} = **{N}/5**

---

## 1) 一句话 Why-read
**Key claim + key observation：** {ONE_PARAGRAPH — what problem, what approach, key result}

---

## 2) CRGP 拆解 Introduction

### C — Context
{2–3 sentences on research background and why this matters}

### R — Related work
{Bullet list of prior approaches grouped by methodology}

### G — Gap
{2–3 sentences: specific limitations of prior work this paper addresses}

### P — Proposal
{2–3 sentences: proposed solution and key insight}

---

## 3) Figure 区
{For each key figure — skip section if figures unavailable}

- **Fig N** ({description}):
  ![figN]({arxiv_html_figure_url_or_omit_if_unavailable})
  {One-line interpretation of what the figure shows}

---

## 4) Experiments — Key Numbers

### Main Results
| Benchmark | Metric | This Work | Best Baseline | Delta |
|-----------|--------|-----------|---------------|-------|
| {task} | {metric} | {value} | {value} | {+X%} |

### Ablation
{Key ablation findings with numbers — which components matter most}

### Limitations
{2–3 honest limitations stated or implied by the paper}

---

## 5) Why it matters — 对研究的启发
{2–4 numbered insights connecting to AI recording devices / wearable sensing research}

1. {Insight 1}
2. {Insight 2}
3. {Insight 3}

---

## 6) Actionable next steps
- [ ] {Follow-up action 1}
- [ ] {Follow-up action 2}
- [ ] {Follow-up action 3}

---

## 7) 评分解释
**{N}/5（Base {B} + Quality {Q} + Observation {O}）**
- Base {B}: {reason}
- Quality {Q}: {reason}
- Observation {O}: {reason}
```

### Key rules:
1. **Use real numbers** — never write "XX" or placeholder values
2. **Figures:** include arXiv HTML URLs when available; omit `![fig]()` if not
3. **Tables:** pipe format for GitHub/Obsidian compatibility
4. **Language:** technical terms in English, analysis in Chinese; both are fine
5. **Scoring math must be explicit** — show the component breakdown

---

## 🔄 Step 5 — Update papers.json + Regenerate kanban.html

### 5a. Update papers.json

Load `output/papers.json`.

If the paper **was found** in papers.json (Step 2):
- Set `status` = `"reading"`
- Set `note_path` = `"output/notes/{paper_id}.md"`
- Set `last_updated` to today's date

If the paper **was NOT found** (read directly without going through kanban):
- Create new paper entry with all available fields
- Set `status` = `"reading"`, `note_path` = the saved file path
- Add to `papers` array

Save updated `output/papers.json`.

### 5b. Regenerate kanban.html

Load template from `../.claude/skills/conference-scout/templates/kanban.html`.

**Compute all template values** (same as conference-scout Step 5e):

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
| `{{READING_PAPERS}}` | HTML cards for reading papers (this paper now here) |
| `{{DONE_PAPERS}}` | HTML cards for done papers |
| `{{UNREAD_EMPTY}}` | empty state div if 0 unread, else empty string |
| `{{READING_EMPTY}}` | empty state div if 0 reading, else empty string |
| `{{DONE_EMPTY}}` | empty state div if 0 done, else empty string |

**Paper card HTML** (same format as conference-scout):
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

For papers with `note_path` set:
- `{{NOTE_BTN}}` = `<a href="{{NOTE_PATH}}" class="btn btn-done">📄 Notes</a>`
- `{{NOTE_LINK}}` = `<a href="{{NOTE_PATH}}" class="note-link">📝 Reading notes →</a>`

Save to `output/kanban.html` (overwrite).

---

## 📋 Step 6 — Chat Summary

```
📝 DNL Complete — {ALIAS}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 {TITLE}
👤 {AUTHORS} | 📍 {VENUE} {YEAR} | ⭐ {RATING} ({N}/5)
🔗 {URL}

💡 核心发现: {WHY_READ — one sentence}
📊 关键数据: {BEST_RESULT — top metric + number}
✨ 启发: {TOP_INSIGHT — one sentence connecting to your research}

💾 Notes → output/notes/{paper_id}.md
🌐 Kanban updated → output/kanban.html  (moved to Reading column)
```

---

## ⚠️ Error Handling

| Error | Action |
|-------|--------|
| arXiv HTML 404 | Use abstract page only; note `[Full text unavailable]` |
| Non-arXiv paper, no full text | Use abstract + SS metadata; note clearly |
| Paper not in papers.json | Create new entry, proceed normally |
| papers.json malformed | Recreate from scratch; warn user |
| Very long paper (>50 pages) | Focus on Abstract, Intro, Method summary, Results tables, Conclusion |
| No figures in HTML | Skip Figure section; note `[No figures extracted]` |
