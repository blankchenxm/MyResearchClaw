# MyResearchClaw 🦀

> **Turn top-venue papers into structured intelligence — search, read, and map implementations, all from a single local server.**

MyResearchClaw is an **AI-powered research workflow** built on top of Claude Code (claude-code CLI). You point it at a topic, and it hunts down the most relevant papers from the top conferences, deep-reads them into richly structured Chinese notes, and maps out real-world engineering implementations — all persisted to a clean web dashboard you open in your browser.

No cloud account needed. No SaaS subscription. Just a local Python server and the Claude CLI.

---

## What It Does

### 1. Research — 调研

**Conference Scout** finds the papers. **Paper Reader** reads them deeply. Together they give you a chronological, role-annotated timeline of a research topic — from foundational breakthroughs to frontier work — plus a per-paper reading note with figures, evidence, and analysis.

### 2. Engineering Intelligence — 工程实现

**Engineering Scout** maps the implementation landscape for the same topic: paper-linked repos, independent open-source projects, commercial products, and ecosystem signals. It synthesizes a Technology Readiness assessment so you know exactly where the field sits on the research-to-deployment spectrum.

---

## The Three Skills

### 🔍 Conference Scout

> *"7-round iterative search that finds the papers keyword search misses."*

Conference Scout doesn't just run a keyword query and dump results. It runs a disciplined **7-round pipeline**:

| Round | What happens |
|---|---|
| **0 — Query Expansion** | LLM expands the raw topic into 3–5 complementary queries: synonyms, abbreviations, sub-concepts, known system names |
| **1 — Discovery** | Broad Semantic Scholar sweep via survey/review queries; builds vocabulary and identifies anchor papers |
| **2 — Anchor Extraction** | LLM produces a structured JSON: system names, recurring authors, key phrases, series clusters, negative patterns, subfield boundary |
| **3 — Precision Search** | DBLP venue scans (year-by-year, including companion tracks) + author sweeps for every `series_clusters` entry. Finds papers with novel system names that keyword search can't reach |
| **4 — Relevance Gate** | Every candidate checked against `subfield_boundary` and `negative_patterns`. Venue alone is not sufficient — top venues contain many off-topic papers |
| **4.5 — Confirmation Pause** | Shows a lightweight table (title / venue / year / citations / PDF availability) and **waits for you to confirm** before proceeding. You can tighten or relax the constraints |
| **5 — Citation Expansion** | For top-3 frontier papers: fetch references (co-citation → foundation candidates) and citations (recent tier-1 → new frontier candidates) |
| **6 — Timeline Assembly** | Classifies every survivor into `survey / breakthrough / foundation / consolidation / frontier` by citation structure and related-work language, not just year |
| **7 — Final Output** | Writes to `output/papers.json` and generates the topic dashboard at `output/projects/{slug}/papers.html` |

**Data sources (priority order):** DBLP → Semantic Scholar (with `openAccessPdf`, `influentialCitationCount`) → arXiv → Google Scholar fallback.

**Venue groups supported:**

| Group | Conferences |
|---|---|
| `ai_ml` | NeurIPS, ICLR, ICML, AAAI, CVPR, ACL, EMNLP |
| `iot_systems` | MobiCom, MobiSys, SenSys, UbiComp/IMWUT, IPSN |
| `wearable_sensing` | SenSys, IMWUT, MobiSys, CHI, UIST |
| `eda_hardware` | DAC, ICCAD, DATE, ASP-DAC, ISLPED |
| `networking` | SIGCOMM, NSDI, INFOCOM |
| `systems` | OSDI, SOSP, ATC, EuroSys |
| `security` | USENIX Security, CCS, IEEE S&P, NDSS |
| `hci` | CHI, UIST, CSCW |

---

### 📖 Paper Reader

> *"15-step evidence-first pipeline that turns one PDF into a 12-section structured Chinese note."*

Paper Reader is not a summarizer. It extracts structured evidence from the PDF first, then the model writes — grounded in that evidence and gated by a lint pass.

**Accepted inputs:** arXiv URL · arXiv ID · DOI URL · ACM DL URL · local PDF path · paper ID from `papers.json`

**PDF acquisition cascade (5 steps):**
1. Local PDF already in `output/pdfs/`
2. arXiv direct PDF
3. Semantic Scholar `openAccessPdf.url`
4. OpenAlex `best_oa_location.pdf_url` (DOI-driven)
5. Unpaywall `best_oa_location.url_for_pdf` (DOI-driven)

If all 5 fail, the UI shows a **drag-and-drop upload zone** so you can drop the PDF manually — the pipeline auto-resumes after upload.

**The 15-step pipeline:**

| Steps | Actor | What it produces |
|---|---|---|
| 1 — resolve identity | `resolve_paper.py` | normalized paper ID, arXiv/DOI |
| 2 — collect metadata | `collect_metadata.py` | authors, venue, year, affiliations, citations |
| 3 — fetch PDF | `fetch_pdf.py` | local PDF at `output/pdfs/{topic_slug}/{paper_id}.pdf` |
| 4 — extract source text | `extract_source_text.py` | section-chunked text manifest |
| 5 — extract evidence | `extract_evidence.py` | claims, numbers, comparisons per section |
| 6 — extract figure assets | `extract_pdf_assets.py` | figure crops + captions |
| 7 — plan figures | `plan_figures.py` | figure placement decisions |
| 8 — figure/table decisions | `plan_figure_table_decisions.py` | which figures go in the note |
| 9 — synthesis bundle | `build_synthesis_bundle.py` | unified reading context for the model |
| 10 — note plan | **model** | `note_plan.json` with section-by-section evidence map |
| 11 — grounding lint | `lint_grounding.py` | every substantive section must cite a valid `section_id` |
| 12 — draft note | **model** | 12-section Chinese Markdown note |
| 13 — style lint | `lint_note.py` | `passes_style_gate: true` required to proceed |
| 14 — quality review | **model** | 7-question self-check; revises if needed |
| 15 — persist | `write_note.py` | writes `output/notes/{topic_slug}/{paper_id}/note.md`, updates `papers.json` |

**The note template — 12 fixed sections:**

```
## 核心信息            fixed metadata block
## 原文摘要翻译        faithful Chinese translation (not a rewrite)
## 创新点
## 一句话总结
## 研究问题
## 数据与任务定义
## 方法主线
   ### 机制流程        3–4 step numbered flow
## 关键结果
## 深度分析
## 局限
## 我的笔记
## 引用
```

Math renders in the note view via **KaTeX** (`$...$` inline, `$$...$$` display). Figures are cropped from the PDF and embedded as images.

**Real-time progress:** the dashboard shows file-based progress (not fake time ticks) — the progress bar advances as each pipeline artifact appears: *正在获取 PDF... 38%* → *正在提取证据... 58%* → *Claude 正在撰写笔记... 88%* → done.

---

### 🛠️ Engineering Scout *(in active development)*

> *"Three-ring implementation map + Technology Readiness assessment."*

Engineering Scout searches the same topic from the engineering angle. It organizes findings into three concentric rings:

| Ring | What it finds |
|---|---|
| 1 — Paper-linked | repos and artifacts directly produced by the papers in your timeline |
| 2 — Independent | GitHub projects solving the same problem independently; assessed for maturity and adoption |
| 3 — Ecosystem | startups, products, funding signals, technical blog posts, community activity |

It produces a **Technology Readiness** level (`research_only` → `early_prototype` → `active_development` → `commercial_traction` → `mature_ecosystem`) with a gap analysis and a concrete "best entry point for an engineer today."

*This skill is being actively extended — better cross-linking with the paper timeline, inline GitHub stars, and commit-recency signals are coming.*

---

## Getting Started

### Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) (`claude` binary in `PATH`)
- Conda environment with PyMuPDF (for PDF text extraction):

```bash
conda create -n myresearchclaw python=3.10
conda activate myresearchclaw
pip install pymupdf requests
```

### Run the server

```bash
git clone https://github.com/blankchenxm/MyResearchClaw.git
cd MyResearchClaw
python serve.py
```

Then open **http://localhost:5678** in your browser. That's the **Topic Navigator** — your home page for all research themes.

The server handles everything: paper state, PDF delivery, note rendering, progress polling, and the conference-scout workflow UI.

### Start a research session

1. Open http://localhost:5678
2. Click **+ New Research Theme** on the Topic Navigator
3. Enter topic, year range, and venue group
4. Conference Scout runs its 7-round pipeline; at Round 4.5 it pauses and shows you the candidate table for confirmation
5. After you confirm, it finishes and the topic card appears on the navigator
6. Click **Open Papers** → topic dashboard with the full timeline
7. Hit **精读论文** on any paper card to deep-read it — progress updates live

### Manual PDF upload

If automatic PDF fetch fails (paywalled, anti-bot blocked), the paper card shows a drag-and-drop zone. Drop the PDF there and the pipeline auto-resumes.

---

## Project Layout

```
serve.py                          local HTTP server + all workflow orchestration
SKILL.md                          project-level skill index for Claude Code
skills/
  conference-scout/
    SKILL.md                      7-round search protocol
    assets/kanban.html            dashboard + Topic Navigator template
    references/                   venue registry, API cookbook
  paper-reader/
    SKILL.md                      15-step pipeline spec
    scripts/                      run_pipeline.py + all extraction scripts
    assets/note_template.md       12-section note skeleton
    references/                   evidence-first contract, paper types, writing guide
    tests/                        pytest suite for pipeline scripts
  engineering-scout/
    SKILL.md                      3-ring implementation search protocol
    assets/engineering.html       engineering page template
references/
  api-cookbook.md                 curl templates: S2, DBLP, OpenAlex, Unpaywall
  pdf-cascade.md                  PDF acquisition step-by-step
  site-patterns/                  per-site quirks (S2 rate limits, arXiv redirects…)
scripts/
  cdp-proxy.mjs                   Chrome DevTools Protocol proxy for anti-bot fallback
  check-deps.sh                   environment check before CDP fallback
output/                           gitignored — all runtime artifacts live here
  papers.json
  kanban.html
  projects/{slug}/papers.html
  projects/{slug}/engineering.html
  notes/{slug}/{paper_id}/note.md
  pdfs/{slug}/{paper_id}.pdf
```

---

## Persistent State

| File | Purpose |
|---|---|
| `output/papers.json` | Single source of truth: all papers, metadata, reading status, note paths |
| `output/token_usage.json` | Token usage log per operation |
| `output/kanban.html` | Topic Navigator (root page) |
| `output/projects/{slug}/papers.html` | Per-topic timeline dashboard |
| `output/projects/{slug}/engineering.html` | Per-topic engineering report |
| `output/notes/{slug}/{paper_id}/note.md` | Deep-reading note + figures |

Paper lifecycle: `unread` → `reading` (with live %-progress) → `done`

---

## Roadmap

- [ ] **Engineering Scout v2** — inline GitHub activity, cross-linked with paper timeline cards
- [ ] **Multi-topic comparison view** — side-by-side timeline across themes
- [ ] **Hosted mode** — lightweight deployment on a personal server; open the HTML directly without running `serve.py` locally
- [ ] **Export** — Obsidian vault sync, Zotero-compatible BibTeX export
- [ ] **Conference Scout: auto-refresh** — scheduled re-runs to catch newly published papers

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MYRESEARCHCLAW_MODEL` | `claude-sonnet-4-6` | Claude model for all agentic steps |
| `MYRESEARCHCLAW_CLAUDE_BIN` | `claude` | Path to the Claude Code binary |
| `MYRESEARCHCLAW_PORT` | `5678` | HTTP server port |

---

## Quick health check

```bash
curl http://localhost:5678/api/health
curl http://localhost:5678/api/papers
```
