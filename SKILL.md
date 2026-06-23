---
name: my-research-claw
description: Search top-conference papers by topic, deep-read one paper into a 12-section Chinese note with figures, and pull engineering signals (GitHub repos, products) for the same topic. Backed by an HTML dashboard at localhost:5678 with buttons for "📖 精读论文" / "📄 查看笔记" / "Generate Engineering View", plus a project chat. Three sub-skills under skills/ — conference-scout, paper-reader, engineering-scout — share one papers.json database and one PDF cascade. Use this when the user wants to find papers, 精读 a paper, or investigate engineering implementations on a topic; trigger phrases include 搜论文, 顶会论文, find papers, 精读论文, read this paper, conference papers, and arXiv/DOI links with reading intent. Do NOT activate for questions about a paper the user already read (no fetch needed), for code debugging without literature intent, or for general project-meta questions.
---

# MyResearchClaw

Turns one of "find papers on X" / "deep-read this paper" / "find engineering signals on X" into a persistent dashboard + Chinese note + figures, all stored under `output/`.

## Architecture

```
                          HTML buttons                       chat
  output/projects/                                            ▼
    {slug}/papers.html  ──┐         POST /api/read-paper      claude CLI
                          ├──► serve.py ──► /api/chat ──────► (claude-sonnet-4-6)
    {slug}/engineering.html       /api/generate-engineering    │
                          │                                    │
  output/kanban.html  ────┘                                    │
                                                               ▼
                                                     reads SKILL.md +
                                                     skills/{name}/SKILL.md
                                                               │
                                              ┌────────────────┼────────────────┐
                                              ▼                ▼                ▼
                                       conference-scout   paper-reader  engineering-scout
                                       (find papers)      (15-step pipe) (GitHub/products)
                                              │                │                │
                                              ▼                ▼                ▼
                                       output/papers.json  + output/notes/{slug}/{id}/note.md
                                                              + output/pdfs/{slug}/{id}.pdf
```

## Usage

### 0. First-time setup

```bash
cd /home/meng/Agent/MyResearchClaw
bash scripts/check-deps.sh                                  # only if you'll use Google Scholar (CDP)
/home/wangmingke/anaconda3/envs/derm-vlm/bin/python -c "import fitz"   # confirm PyMuPDF for paper-reader
```

`check-deps.sh` is **not required** for normal arXiv / S2 / DBLP / OpenAlex / Unpaywall workflows. Only run it before the first task that touches Google Scholar.

### 1. Start the dashboard

```bash
cd /home/meng/Agent/MyResearchClaw
python serve.py
```

Open http://localhost:5678/kanban.html — main entry. Topic pages are at
`http://localhost:5678/projects/{topic_slug}/papers.html`.

### 2. Find papers (conference-scout)

**No HTML button for this** — start it from chat:

```
帮我搜索 silent speech EMG 在 SenSys / IMWUT 2024-2025 的论文
```

The skill writes results to `output/papers.json` and renders `output/projects/{slug}/papers.html`. Workflow has a built-in pause after Round 4 — it shows a candidate table and waits for confirmation before doing citation expansion.

### 3. Deep-read one paper (paper-reader)

**Two ways:**

- HTML: click `📖 精读论文` on any paper card → `POST /api/read-paper` → serve.py spawns
  `claude -p ... --model claude-sonnet-4-6` in the background. Progress shows on the kanban.
- Chat: `精读 https://arxiv.org/abs/2603.02847`

The pipeline has 15 steps (see `skills/paper-reader/SKILL.md`). Steps 1-9 are batched in one shot:

```bash
/home/wangmingke/anaconda3/envs/derm-vlm/bin/python \
  skills/paper-reader/scripts/run_pipeline.py \
  --input "https://arxiv.org/abs/2603.02847" \
  --paper-id "silentwear-...-2026" \
  --topic-slug "silent-speech-recognition-emg-llm" \
  --papers-json output/papers.json \
  --prefix silentwear
```

When done, the note is at `output/notes/{slug}/{paper_id}/note.md` and figures at
`output/notes/{slug}/{paper_id}/figures/`. Click `📄 查看笔记` to read.

### 4. View an existing note

Click `📄 查看笔记` on the card → `GET /api/notes/{paper_id}` → renders markdown.
Figure references like `figures/fig1.png` are auto-rewritten to
`/api/notes/{paper_id}/figures/fig1.png` so images load inline.

### 5. Engineering signals (engineering-scout)

Click `Generate Engineering View` on a topic page → `POST /api/generate-engineering` →
writes `output/projects/{slug}/engineering.html`.

### 6. Per-page chat

Click the `💬` icon on a topic page → `POST /api/chat` → `claude -p ... --output-format json`
single-turn Q&A, anchored to the current topic context. Does not invoke any skill, does not write to disk.

## File layout

| Path | What |
|---|---|
| `output/papers.json` | Single source of truth — all papers across all topics |
| `output/kanban.html` | Main dashboard |
| `output/projects/{slug}/papers.html` | Per-topic kanban |
| `output/projects/{slug}/engineering.html` | Per-topic engineering report |
| `output/pdfs/{slug}/{paper_id}.pdf` | Downloaded PDFs (input to paper-reader) |
| `output/notes/{slug}/{paper_id}/note.md` | Final Chinese精读 note |
| `output/notes/{slug}/{paper_id}/figures/` | Materialized figures referenced by the note |
| `output/tmp/{paper_id}/` | Paper-reader pipeline intermediates (safe to delete) |
| `output/logs/{paper_id}.log` | Claude CLI stdout for that paper's read run |

## Sub-skills

- `skills/conference-scout/SKILL.md` — 6-round search (Discovery → Anchors → Precision → Relevance gate → **Round 4.5 candidate confirmation pause** → Citation expansion → Timeline). Reads `references/api-cookbook.md`, `references/pdf-cascade.md` for shared logic.
- `skills/paper-reader/SKILL.md` — 15-step evidence-first pipeline ending in a 12-section Chinese note. Required interpreter `/home/wangmingke/anaconda3/envs/derm-vlm/bin/python` (has PyMuPDF). Required output schema: `pipeline_status=complete`, `status=done`, `progress=100`, `note_path`, `figures_dir` all written to `papers.json` by `write_note.py`.
- `skills/engineering-scout/SKILL.md` — three-ring search for GitHub repos, products, deployment signals.

## Shared references

Don't reinvent these. All three sub-skills consult them:

- `references/pdf-cascade.md` — 5-step PDF acquisition (arXiv → S2 → OpenAlex → Unpaywall → Google Scholar CDP). Writes `full_text_status` enum into `papers.json`.
- `references/api-cookbook.md` — curl templates for arXiv / Semantic Scholar / DBLP / OpenAlex / Unpaywall / Google Scholar.
- `references/site-patterns/semanticscholar.org.md` — S2 traps (`externalIds.ArXiv` case sensitivity, `openAccessPdf=null` misread, 429 → switch to DBLP immediately).

## Config (env vars)

| Var | Default | Purpose |
|---|---|---|
| `MYRESEARCHCLAW_MODEL` | `claude-sonnet-4-6` | Model for HTML-triggered skill runs |
| `MYRESEARCHCLAW_CLAUDE_BIN` | `claude` | Path to claude CLI |
| `CDP_PROXY_PORT` | `3456` | CDP proxy port (only for Google Scholar fallback) |

S2 API Key strongly recommended — without it ~100 req/5min triggers 429 forcing fallback to DBLP. Get one at https://www.semanticscholar.org/product/api#api-key-form and pass it as `x-api-key` header.

## When things go wrong

| Symptom | Where to look |
|---|---|
| Paper card stuck on "⏳ 精读中... 20%" after restart | Check `papers.json`: if `pipeline_status=complete` and `note_path` exists, the card should auto-show "✅ 已完成" — `render_progress_state` reads `pipeline_status` first. If not, `write_note.py` didn't finish. |
| "📖 精读论文" click does nothing | `output/logs/{paper_id}.log` — Claude CLI stdout |
| Pipeline fails at Step 4 with `PyMuPDF is required` | The agent invoked `python` instead of the derm-vlm interpreter. `run_pipeline.py` should auto-switch — if it didn't, set `MYRESEARCHCLAW_NO_AUTO_SWITCH` is unset, then re-run. |
| Conference scout can't find recent papers | Likely S2 429. Add API key, or wait 5 min. |
| Google Scholar step blocked | Re-run `bash scripts/check-deps.sh` to bring up CDP Proxy. |

## Notes

- **Three sub-skills share one database** (`papers.json`). conference-scout creates entries, paper-reader fills `note_path` + `pipeline_status`, engineering-scout writes its own HTML but doesn't touch papers.json.
- **PDFs are cached** under `output/pdfs/{slug}/`. paper-reader's `fetch_pdf.py` checks this dir first via `--local-pdf-dir` before walking the 5-step cascade.
- **One paper at a time** for精读 — the pipeline is not designed for batch.
