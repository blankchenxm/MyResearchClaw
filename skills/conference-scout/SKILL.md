---
name: conference-scout
description: Iteratively search top-conference papers on one topic, gate by relevance, build a chronological timeline labeled by each paper's role (survey / breakthrough / foundation / consolidation / frontier), and persist to output/papers.json + render output/projects/{slug}/papers.html. Two-pass strategy with a confirmation pause after relevance gating, so the user can adjust constraints before citation expansion runs. Use when the user wants to find / scout / map papers on a topic; triggers include 搜论文, 顶会论文, find papers, scout papers, 调研, conference papers, "[topic] in [conference]". Not for精读 one paper — that's paper-reader.
---

# Conference Scout

Iteratively search top-conference papers, gate by relevance, then assemble a timeline. Output a persistent paper database and topic HTML page.

## Inputs

| Field | Required | Notes |
|---|---|---|
| `topic` | yes | English keywords preferred |
| `venue_group` | yes (auto-inferred if topic is clear) | One of `wearable_sensing` / `ai_ml` / `iot_systems` / `eda_hardware` / `security` / `systems` / `hci`. See `references/venue-registry.md`. |
| `year_start` | no | Auto-inferred from Round 1 results |
| `year_end` | no | Default: current year |
| `specific_venues` | no | Explicit override, bypasses group selection |

If venue intent is missing and topic doesn't auto-route, ask which family before proceeding. For "顶会论文" / "top venues" / "完整调查" / completeness intent — never silently narrow to a hand-picked subset; report the exact venue set searched in the response.

**Tier policy**: Both Tier 1 and Tier 2 venues are actively searched in every run. Tier 1 = primary sweep (enumerate by year in Round 3). Tier 2 = same active search, but if quota or time is tight, deprioritize Tier 2 after Tier 1 is saturated. Never skip Tier 2 silently — if skipped, state it explicitly.

## Data sources (priority order)

1. **DBLP** — venue completeness (`{dblp_url}` + year suffix, e.g. `dblp.org/db/conf/sensys/sensys2024.html`). Use this to confirm "did this paper appear in SenSys 2024?" — DBLP's `venue` is human-curated, Semantic Scholar's auto-assigned `venue` string is not reliable.
2. **Semantic Scholar** — metadata + citations / references. Always pass `fields=title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue,publicationTypes` — defaults are too thin. Use `influentialCitationCount` (not `citationCount`) to assess foundation status.
3. **arXiv** — supplement for very recent / preprint-only work. Keep only when ≥ 2 non-generic topic keywords match and no venue-confirmed version exists.
4. **Google Scholar (CDP)** — last-resort fallback. Only when DBLP + S2 + arXiv together can't confirm latest state.

Full curl templates: `../../references/api-cookbook.md`.
S2 traps (`externalIds.ArXiv` case, `openAccessPdf=null` misread, 429 handling): `../../references/site-patterns/semanticscholar.org.md`.

## Workflow

7 rounds. Log which round you are in. Don't skip rounds. Don't merge rounds.

### Round 0 — Query Expansion *(LLM only, no API)*

Expand the raw topic into 3-5 complementary queries covering:
- synonyms: `EMG` → `electromyography`, `surface EMG`, `myoelectric`
- abbreviations both ways: `IoT ↔ Internet of Things`
- sub-concepts: `silent speech` → `silent speech recognition`, `non-audible speech`, `articulatory gesture`
- known anchors: famous system names in the field (e.g. AlterEgo, EchoSpeech)

### Round 1 — Discovery

Run these in order on Semantic Scholar, stop early if survey coverage is rich:

1. `{topic} survey`
2. `{topic} review`
3. `{topic} tutorial`
4. `a survey of {topic}`
5. Survey thin? → `{topic}` scoped to most relevant tier-1 venue + recent year

Read abstracts. Note system / task / metric vocabulary. Don't filter by venue here — discovery is intentionally broad.

### Round 2 — Anchor Extraction *(LLM only, no API)*

Produce this JSON before proceeding:

```json
{
  "system_names": [],         // proper-noun systems seen
  "author_names": [],         // recurring authors
  "key_phrases": [],          // technical noun phrases specific enough to quote
  "venue_year_pairs": [],     // e.g. ["SenSys 2023", "IMWUT 2024"]
  "breakthrough_candidates": [],  // papers called "first" / "seminal" / "foundational"
  "survey_candidates": [],
  "constraint_terms": [],     // 1-2 words narrowing topic to intended subproblem
  "negative_patterns": [],    // recurring false-positives to exclude in Round 4
  "subfield_boundary": "",    // one sentence: where intended topic ends, adjacent fields begin
  "series_clusters": []       // author groups with ≥2 papers found — flag for deep sweep in Round 3
}
```

**Series detection rule:** If ≥ 2 papers share a first or last author, treat them as a research program. Add the group to `series_clusters` and schedule a full author DBLP sweep in Round 3 — the same group likely has sibling papers at other venues in the same publication cycle.

### Round 3 — Precision Search

Convert each anchor into a query:

| Anchor | Query form |
|---|---|
| system name | `"SystemName"` |
| author name | `"Author Name" {topic}` |
| key phrase | `"exact technical phrase" {context}` |
| venue + year | `{topic} {constraint_terms}` scoped to `{venue} {year}` |

**Two mandatory checks — do not skip:**

1. **DBLP venue scan**: For each target venue × latest 2 years, fetch `dblp.org/db/conf/{key}/{key}{year}.html` and scan all titles. Keyword search cannot discover papers with novel system names; venue scanning can. Also check companion/workshop tracks (`{key}{year}c.html`). If a year returns nothing, note it and move on.

2. **Author sweep**: For every anchor paper and every `series_clusters` entry, search its first 2 authors on DBLP (`site:dblp.org "{Author Name}"`). The same group routinely publishes sibling papers at different venues in the same cycle; author sweep finds what keyword search misses.

Don't trust S2's `venue` field alone for tier-1 confirmation.

### Round 4 — Relevance Gate *(LLM only, no API)*

Every candidate must pass all three:

1. About the specific subproblem (not just a nearby field sharing keywords)? Use `subfield_boundary` as the reference line.
2. Matches intended context (device / scenario / population / system layer)?
3. Contributes to the timeline, not just shares surface keywords?

Reject if it matches `negative_patterns`, is outside `subfield_boundary`, or is a workshop version of a venue-confirmed paper already in the pool. Venue alone is not sufficient — top venues contain many off-topic papers.

### Round 4.5 — Candidate Confirmation *(PAUSE)*

Before Round 5, show the user a lightweight table and wait for confirmation:

```
| # | 标题 | Venue | 年份 | 引用 | influential | PDF |
|---|------|-------|------|------|-------------|-----|
| 1 | ... | SenSys | 2024 | 87 | 23 | ✓ arXiv |
| 2 | ... | IMWUT  | 2023 | 142 | 41 | ✗ |
```

PDF column is quick precheck only — `✓ arXiv` if `arxiv_id` set; `✓ S2` if `openAccessPdf.url` non-null; otherwise `✗`. Do NOT run the full PDF cascade here (OpenAlex / Unpaywall / Google Scholar) — that belongs to paper-reader.

Ask: `共 {N} 篇通过 Round 4，是否继续 Round 5-7？或需要调整 negative_patterns / constraint_terms？`

Only proceed after the user confirms. If the user adjusts, re-run Round 4 with the new rubric and present the table again.

### Round 5 — Citation Expansion

After confirmation, and only if Round 3 produced ≥ 3 anchor papers that passed Round 4:

1. For top-3 frontier papers from Round 3 → fetch `references` via S2 → union → sort by co-occurrence frequency. Papers co-cited by ≥ 2 frontier papers → strong foundation / consolidation candidates.
2. For each top-3 anchor → fetch `citations`, sort by year descending. Recent + tier-1 venue → new frontier candidates.
3. For each `series_clusters` entry → fetch the group's full recent publication list from their DBLP author page and check for any on-topic paper not yet in the pool.

Foundation elevation signals: high `influentialCitationCount / citationCount` ratio; described as "first" / "seminal" / "pioneering" in multiple frontier papers' related-work sections.

### Round 6 — Timeline Assembly

Classify every Round-4 survivor into exactly one role:

| Role | Definition |
|---|---|
| `survey` | field-wide literature map |
| `breakthrough` | introduced a key concept the community treats as foundational |
| `foundation` | early core papers that established the baseline (may overlap breakthrough) |
| `consolidation` | between foundations and frontier; show how the field branched |
| `frontier` | recent tier-1 papers, current strongest direction |

Role is by citation structure + related-work language, NOT by year. A 2023 paper can be `breakthrough`; a 2019 paper can still be `frontier` in a young field. Low confidence → prefer `consolidation` over inventing certainty.

Sort chronologically within and across roles. Timeline is continuous; role is an annotation.

### Round 6.5 — Token Usage Record *(LLM only, no API)*

After timeline is finalized, write one record to `output/token_usage.json`:

```python
import json, os
from datetime import datetime

path = "output/token_usage.json"
data = json.load(open(path)) if os.path.exists(path) else {"operations": []}
# Estimate: count WebSearch + WebFetch calls made across all rounds (each ~2K input tokens avg)
# Count output: approximate by response length (~4 chars per token)
api_calls = {TOTAL_API_CALLS}  # substitute actual count
est_input = api_calls * 2000 + {CONTEXT_SIZE_ESTIMATE}
est_output = len({RESPONSE_TEXT}) // 4
data["operations"].append({
    "type": "conference-scout",
    "entity_id": "{TOPIC_SLUG}",
    "title": "{TOPIC}",
    "date": datetime.now().strftime("%Y-%m-%d"),
    "input_tokens": est_input,
    "output_tokens": est_output,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cost_usd": 0,
    "duration_ms": 0,
    "note": "estimated — conference-scout runs in main session"
})
data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
json.dump(data, open(path, "w"), ensure_ascii=False, indent=2)
```

Fill `{TOTAL_API_CALLS}` with actual WebSearch + WebFetch count from this run.
Fill `{CONTEXT_SIZE_ESTIMATE}` with a rough estimate based on SKILL.md + papers.json size (~8000 for typical run).
Fill `{TOPIC_SLUG}` and `{TOPIC}` from the run's inputs.
Fill `{RESPONSE_TEXT}` with `repr(response_text)` or use `len(full_response_markdown)`.

If write fails (e.g. file locked), skip silently — do not block the final response.

### Round 7 — Final Output

Target counts:
- `survey`: 1-3
- `breakthrough` / `foundation`: 2-4
- `consolidation`: 3-5
- `frontier`: 4-8
- arXiv supplements (no venue): up to 3, labeled

Ranking within each role: (1) relevance to the user's constraints; (2) timeline-role usefulness for the query (breakthrough > consolidation for foundational context; frontier > consolidation for "latest" queries); (3) tier-1 confirmation; (4) recency for frontier, `influentialCitationCount` for foundation.

Never let high-citation older loose matches crowd out clearly on-topic recent tier-1 papers.

## Latest-paper safeguard

When the user asks for recent / latest:
- verify ≥ 1 tier-1 paper from the newest year in range exists
- if none, say so explicitly and report the most recent tier-1 result found
- always reference concrete years in the response (`SenSys 2025`), never just "latest"
- a tier-2 hit does NOT satisfy this safeguard if tier-1 came up empty

## Summaries

For each retained paper, generate `summary_en` and `summary_zh` (4-6 sentences each).

- Concrete technical detail > generic praise
- Mention at least one of: mechanism / metric / architecture choice / benchmark result / deployment constraint
- Survey papers → summarize the taxonomy or periodization the survey imposes
- Write as a research brief, not an abstract rewrite

## Outputs

### `output/papers.json`

Append/update each paper. Schema (relevant fields):

```json
{
  "id": "{slug}",
  "title": "...",
  "authors": "First Author et al.",
  "year": 2024,
  "venue": "IMWUT",
  "venue_tier": 1,
  "citations": 37,
  "influential_citations": 12,
  "url": "https://doi.org/...",
  "arxiv_id": "2401.XXXXX",
  "timeline_role": "frontier",
  "timeline_reason_zh": "首次在 AR 眼镜上端侧 neural beamforming, 被后续工作广泛引用",
  "summary_en": "...",
  "summary_zh": "...",
  "status": "unread",
  "topic": "{topic}",
  "topic_slug": "{slug}",
  "tags": []
}
```

Dedupe by `url`. Preserve existing `status` / `progress` / `note_path` / `pipeline_status` / `figures_dir` on re-search.

Append the search itself to `output/papers.json.searches[]`:

```json
{ "topic": "...", "date": "...", "year_range": "...", "venues_checked": ["SenSys 2024", ...], "papers_added": 7 }
```

### `output/projects/{topic_slug}/papers.html`

Generate from `assets/kanban.html`. serve.py / the layout handles the placeholders ({{LAST_UPDATED}}, {{TIMELINE_ITEMS}}, etc.) — you just need to write the data.

Render a continuous chronological timeline with role annotations, paper cards showing `timeline_role` + bilingual role reasoning + reading progress + note links + venue tier badge.

For topic-specific HTML requests, still update `output/papers.json` and generate `output/projects/{topic_slug}/papers.html` — do NOT overwrite the shared `output/kanban.html`.

## Response

```
Conference Scout — {TOPIC}
{YEAR_RANGE} | {VENUES_CHECKED}

Rounds: Discovery → Anchors → Precision → Gate → [pause confirmed] → Citation → Timeline

{N} new papers added | {TOTAL} total tracked

Timeline summary:
  Survey: {N}   Breakthrough/Foundation: {N}   Consolidation: {N}   Frontier: {N}   arXiv: {N}

[Foundation / Breakthrough]
1. {Title} ({Venue} {Year}, {citations} cites)
   Role: {timeline_reason_zh}
   {summary_zh}

[Frontier]
2. {Title} ({Venue} {Year})
   Role: ...
   {summary_zh}

Venues checked:
  Tier 1: SenSys 2024/2025, IMWUT 2024/2025, ...
  Tier 2: (cross-check only)

Dashboard: output/projects/{topic_slug}/papers.html
```

## Failure signals

Read the **含义** before picking an action. Don't reflexively retry.

| 信号 | 含义 | 方向调整 |
|---|---|---|
| S2 `429` | session 配额耗尽，不是瞬时波动 | 立刻切 DBLP，不重试 S2 |
| S2 网络失败 | 单次瞬时故障 | 重试 1 次；仍失败切 DBLP |
| DBLP 页面 5xx | 静态页对抓取不友好 / 当前不可用 | 改用 DBLP search API |
| 同一方式重试 3 次无改善 | 路径错了，不是还没找到 | 换平台或换关键词 |
| Round 4 拒绝 > 80% 候选 | query 太宽或 negative_patterns 太严 | 暂停告知用户；放宽一个条件重新 gate |
| 无任何 venue-confirmed 论文 | 顶会未覆盖该子方向 / 主题词被换说法 | 显示最佳未过滤匹配（标 unconfirmed）；回 Round 0 重扩 query |
| Round 4.5 暂停后用户改条件 | 用户不接受当前候选集 | 用新条件重跑 Round 4，重新呈现表，不要直接进 Round 5 |
| `papers.json` malformed | 文件结构损坏 | recreate with warning，先备份，不要静默覆盖 |
