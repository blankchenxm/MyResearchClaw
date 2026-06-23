---
name: paper-reader
description: Deep-read one academic paper from an arXiv URL, DOI, ACM URL, bare arXiv ID, or local PDF, and produce a 12-section Chinese reading note grounded in PDF evidence. Evidence-first 15-step pipeline — scripts extract text/evidence/figures, the model writes a note_plan JSON then the final note, lint gates style + grounding. Optimized for IoT/wearable/systems papers (systems_iot type), also supports AI_method / benchmark_or_dataset / survey_or_review. Use when the user wants to精读 a specific paper, asks for paper notes, or gives a paper link with reading intent; triggers include 精读, 帮我读, read this paper, paper notes, 深度笔记. Not for searching multiple papers — that's conference-scout.
---

# Paper Reader

Turns one paper into a 12-section Chinese deep-reading note at
`output/notes/{topic_slug}/{paper_id}/note.md` with figures in `figures/`.

Scripts structure the evidence. The model owns understanding, planning, drafting, and final review.

## Required interpreter

```
/home/wangmingke/anaconda3/envs/derm-vlm/bin/python
```

This env has PyMuPDF. The system default `python` (3.8) does not — `extract_source_text.py` fails immediately. `run_pipeline.py` auto-switches if invoked with the wrong interpreter, but use the right one to skip the round trip.

## Language requirement

- Note body in Chinese
- Preserve original-language titles, author names, venue names, metric names, system names
- No mixed Chinese-English clauses (lint will reject)

## Inputs

| Form | Example |
|---|---|
| arXiv URL | `https://arxiv.org/abs/2401.12345` |
| arXiv ID | `2401.12345` |
| DOI URL | `https://doi.org/10.1145/...` |
| ACM URL | `https://dl.acm.org/doi/...` |
| Local PDF path | `output/pdfs/{topic_slug}/{paper_id}.pdf` |
| Paper ID in `papers.json` | `silentwear-...-2026` |

## PDF acquisition

Run `scripts/fetch_pdf.py` with `--papers-json --paper-id --local-pdf-dir output/pdfs/{topic_slug}`. The script walks `../../references/pdf-cascade.md` Step 1-5:

1. Local PDF at `output/pdfs/{topic_slug}/{paper_id}.pdf`
2. arXiv `https://arxiv.org/pdf/{arxiv_id}`
3. S2 `openAccessPdf.url`
4. OpenAlex `best_oa_location.pdf_url` (DOI-driven)
5. Unpaywall `best_oa_location.url_for_pdf` (DOI-driven)

The script writes `full_text_status` into `{prefix}_fetch.json`. Branch on it:

| `full_text_status` | Action |
|---|---|
| `open_pdf` | proceed to extract_source_text |
| `needs_institution` / `no_open_pdf` | **fail closed** — do NOT write a degraded title/abstract-only note |
| `anti_bot_blocked` | Try Google Scholar CDP fallback once (`../../references/api-cookbook.md` § Google Scholar; pre-check `bash ../../scripts/check-deps.sh`). Still blocked → fail closed. |
| `html_not_pdf` | Try one alternative source. Still HTML → fail closed. |
| `unknown` | Rerun cascade with debug logging. Still unknown → fail closed. |

## Pipeline (15 steps)

Steps 1-9 batch in one shot:

```bash
/home/wangmingke/anaconda3/envs/derm-vlm/bin/python \
  skills/paper-reader/scripts/run_pipeline.py \
  --input "{url_or_paper_id}" \
  --paper-id "{paper_id}" \
  --topic-slug "{topic_slug}" \
  --papers-json output/papers.json \
  --prefix {short_prefix}
```

Then Steps 10-15 are model + lint:

| # | Step | Actor | Output |
|---|---|---|---|
| 1 | resolve paper identity | `resolve_paper.py` | `{prefix}_resolve.json` |
| 2 | collect metadata | `collect_metadata.py` | `{prefix}_metadata.json` |
| 3 | acquire PDF | `fetch_pdf.py` | `{prefix}_fetch.json` |
| 4 | extract source text | `extract_source_text.py` | `{prefix}_raw_sections.jsonl` + `{prefix}_source_manifest.json` |
| 5 | extract evidence | `extract_evidence.py` | `{prefix}_evidence.json` |
| 6 | extract figure assets | `extract_pdf_assets.py` | `{prefix}_assets.json` (+ candidate crops in `figures/`) |
| 7 | plan figure placement | `plan_figures.py` | `{prefix}_figures.json` |
| 8 | build figure/table decisions | `plan_figure_table_decisions.py` | `{prefix}_figure_table_decisions.json` |
| 9 | build synthesis bundle | `build_synthesis_bundle.py` | `{prefix}_bundle.json` |
| 10 | write `note_plan.json` | **model** | `{prefix}_note.plan.json` |
| 11 | grounding lint | `lint_grounding.py` | pass / fail |
| 12 | draft note Markdown | **model** | `{prefix}_note.md` |
| 13 | style + structure lint | `lint_note.py --plan-file ...` | `passes_style_gate: true` required |
| 14 | quality + readability review (7-question self-check) | **model** | revised note |
| 15 | persist | `write_note.py --topic-slug ... --paper-id ... --papers-json ...` | writes `output/notes/{topic_slug}/{paper_id}/note.md`, copies figures, updates `papers.json` |

All artifacts live in `output/tmp/{paper_id}/`.

## Stop rules

**Don't skip required steps**, don't merge Step 10 with Step 12, don't declare success while Step 13-15 are pending.

If a step fails: retry → fall back via the allowed path → or stop and name the blocked step. Don't improvise a shortcut.

**Completion language:**

| Phrase | When you may say it |
|---|---|
| `笔记已完成` | Steps 1-15 all done, lint passed, write_note.py succeeded |
| `已生成草稿` | Step 12 done, Step 13-15 not done |
| `已通过校验` | `lint_note.py` actually ran and printed `passes_style_gate: true` |
| early stop | name the current step + still-pending required steps |

## Note plan (Step 10)

Save `output/tmp/{paper_id}/{prefix}_note.plan.json` before drafting. Required fields:

- `paper_type`: `AI_method` / `benchmark_or_dataset` / `survey_or_review` / `systems_iot`
- `paper_type_rationale`: one sentence justifying
- `section_plan`: per-section `###` plan referencing valid `section_id`s from `source_manifest`
- `central_claims[]`: each with `claim` / `evidence` / `proves` / `does_not_prove`
- `claim_boundaries[]`
- `negative_or_limiting_results[]`
- `mechanism_result_map[]`: connect mechanism / design choice → result pattern
- `comparative_positioning[]`: how the paper differs from baselines / prior routes
- `reuse_takeaways[]`
- `followup_questions[]`

Examples + full contract: `references/evidence-first.md`.

Run `lint_grounding.py` before drafting. Every substantive section must cite a valid `section_id` or page range.

## Note template

12 top-level sections, fixed order. Full skeleton: `assets/note_template.md`.

```
## 核心信息            (fixed metadata block, no prose)
## 原文摘要翻译        (faithful Chinese translation, not a rewrite)
## 创新点              (immediately after 原文摘要翻译)
## 一句话总结
## 研究问题
## 数据与任务定义
## 方法主线
   ### 机制流程        (3-4 step numbered flow for method/system/framework papers)
## 关键结果
## 深度分析
## 局限
## 我的笔记
## 引用
```

Required:
- Non-trivial papers → meaningful `###` subheadings in `数据与任务定义` / `方法主线` / `关键结果` / `深度分析`
- Figure placeholders use `> [!figure]` callout
- Materialized images at `output/notes/{topic_slug}/{paper_id}/figures/`, referenced as `figures/fig1.png` (relative)
- Math as `$...$` or `$$...$$`, never code blocks

## Paper type adaptation

12 sections stay identical; typed semantics + `###` subsections differ per type. Full contract: `references/paper-types.md`.

| Type | For | Emphasis |
|---|---|---|
| `AI_method` | NeurIPS / ICLR / CVPR / ICML | model architecture, training objective, ablation interpretation |
| `benchmark_or_dataset` | new benchmarks / datasets / eval protocols | dataset scope, baseline coverage, difficulty distribution |
| `survey_or_review` | tutorials / surveys | taxonomy, periodization, open problems |
| `systems_iot` | SenSys / MobiSys / IMWUT / IPSN / MobiCom | system architecture, module ↔ Challenge mapping, trade-offs, deployment constraints |

Coarse `paper_type` field in `papers.json` maps as: `algorithm → AI_method`, `survey → survey_or_review`, `systems → systems_iot`, `measurement → benchmark_or_dataset`.

## Quality gate

**Fail closed** (do not write) if:
- `full_text_status != open_pdf` and CDP fallback also failed
- `note_plan` did not pass `lint_grounding.py`
- Final note still contains mixed Chinese-English prose (`passes_style_gate: false`)
- Final note misses any of the 12 required sections

**Minimum bar** a note must satisfy:
- Not a paraphrase of the abstract
- Distinguishes 作者声称 from 论文证明
- ≥ 1 real limitation grounded in evidence
- ≥ 1 paper-specific subsection (not just top-level `##`)
- For method-heavy papers: ≥ 1 mechanism `###` subsection detailed enough that an engineer could re-explain the pipeline without reopening the PDF
- Key numbers + central comparison present
- ≥ 1 reusable takeaway

Full checklist: `references/note-quality.md`.

## papers.json schema (relevant fields)

`write_note.py --papers-json --paper-id ...` sets these at Step 15:

```json
{
  "full_text_status": "open_pdf",
  "open_access_status": "green",
  "pdf_url": "https://arxiv.org/pdf/...",
  "pipeline_status": "complete",
  "note_path": "output/notes/{topic_slug}/{paper_id}/note.md",
  "figures_dir": "output/notes/{topic_slug}/{paper_id}/figures",
  "status": "done",
  "progress": 100
}
```

`pipeline_status` enum: `null` → `pdf_ready` → `extracted` → `drafted` → `linted` → `complete`.

## References (load on demand, not by default)

- `references/evidence-first.md` — note_plan structure + evidence-first contract
- `references/paper-types.md` — section semantics per paper type (incl. systems_iot)
- `references/note-quality.md` — minimum bar + quality gate checklist
- `references/workflow.md` — full data contracts per pipeline stage
- `references/figure-placement.md` — placeholder-first figure decisions
- `../../references/pdf-cascade.md` — repo-wide 5-step PDF cascade
- `../../references/api-cookbook.md` — arXiv / S2 / DBLP / OpenAlex / Unpaywall / Google Scholar templates

## Response

```
精读完成 — {ALIAS}
{FULL_TITLE}
{AUTHORS} | {VENUE} {YEAR} | paper_type: {TYPE}

Pipeline:    Step 1-15 all complete
PDF source:  {pdf_source} ({full_text_status})
Lint:        passes_style_gate=true, passes_plan_gate=true

Note:    output/notes/{topic_slug}/{paper_id}/note.md
Figures: output/notes/{topic_slug}/{paper_id}/figures/
```

Stopped early → replace `精读完成` with `已生成草稿` / `PDF 获取失败` / `在 Step N 暂停` and name the pending steps.
