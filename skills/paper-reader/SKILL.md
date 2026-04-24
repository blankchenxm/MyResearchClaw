---
name: paper-reader
description: >
  Deep-read one academic paper from an arXiv URL, DOI, ACM URL, or bare arXiv ID, then generate
  structured reading notes and update the persistent kanban state. Optimized for IoT, systems,
  and wearable sensing papers but works for all venues. Use when the user wants to read, analyze,
  summarize, or extract research insights from a specific paper, especially with phrases such as
  精读, 帮我读, read this paper, paper notes, or when a paper link is given with reading intent.
---

# Paper Reader

Goal: analyze one paper using a three-pass reading strategy, write structured notes to
`output/notes/`, update `output/papers.json`, and regenerate `output/kanban.html`.

Important language requirement:
- write note body primarily in Chinese
- preserve paper titles, author names, venue names, metric names, and system names in original language
- all explanatory prose, analysis, and section content should be Chinese-first

---

## Supported Inputs

- `https://arxiv.org/abs/XXXX.XXXXX`
- `https://arxiv.org/pdf/XXXX.XXXXX`
- `https://doi.org/...`
- `https://dl.acm.org/doi/...`
- bare arXiv ID such as `2401.12345`

---

## Fetch Workflow

### arXiv papers

Fetch in order:
1. `https://arxiv.org/abs/{ARXIV_ID}` — title, authors, abstract, subjects, date
2. `https://arxiv.org/html/{ARXIV_ID}v1` — full text, figures, section structure

If HTML is unavailable, continue with abstract-only analysis and state the limitation explicitly.

### DOI / ACM / other

Fetch the landing page. Extract title, authors, venue, year, abstract.
Use Semantic Scholar to fill missing bibliographic fields.
Do not fabricate unavailable full text; state what is and is not available.

---

## Three-Pass Reading Strategy

Reading happens in three passes. Do not skip to later passes before completing earlier ones.

### Pass 1 — Orientation (abstract, intro, section headings, conclusion)

Answer these questions before reading further:

- What is the one-sentence problem this paper solves?
- What is the research vision — if this system fully worked, what would change in the world?
- What are the claimed contributions (usually bulleted in the intro)?
- Is this primarily a systems paper, an algorithm paper, or a measurement paper?
- Based on section headings: how many challenge/design subsections are there?

If the paper is clearly off-topic or unreadable, stop here and report.

### Pass 2 — Structure (figures, tables, section-level reading without proof details)

Focus on:
- The overview/architecture figure (usually Figure 1 or 2): what are the main components?
- All tables: what metrics, baselines, and results are reported?
- Section structure: map out which section handles which challenge

Answer:
- What are the key results in one sentence each?
- What is the most surprising or strongest result?
- What do the authors not compare against, and why might that be?

### Pass 3 — Deep Read (full text, design rationale, implementation, evaluation)

Read every section with attention to:
- The *why* behind each design decision, not just the *what*
- Where the authors made a trade-off and what they sacrificed
- Implementation constraints (hardware, latency budget, memory, power)
- Whether the experimental setup genuinely supports the claimed contribution

---

## Note Structure

Generate all seven sections. Do not omit sections; use "信息不足，仅从摘要分析" when full
text is unavailable.

```markdown
# 精读笔记 — {ALIAS}

## 0) Metadata
- **Title:** {FULL_TITLE}
- **Alias:** {ALIAS}
- **Authors / Org:** {AUTHORS}
- **Venue / Year:** {VENUE} {YEAR}
- **Links:**
  - Abstract: {URL}
  - HTML: https://arxiv.org/html/{ARXIV_ID}v1  ← omit if not arXiv
  - PDF: https://arxiv.org/pdf/{ARXIV_ID}       ← omit if not available
- **Tags:** {TAGS}
- **My rating:** {N}/5
- **Paper type:** systems | algorithm | measurement | survey

---

## 1) 科研图景与 Vision

> 这篇论文描绘的研究图景是什么？如果系统真的 work，它改变了什么？

{VISION_PARAGRAPH}

作者为什么认为这个问题"现在"值得解决？
{TIMELINESS_PARAGRAPH}

核心 claim（通常是 intro 里的 bullet list）：
- {CLAIM_1}
- {CLAIM_2}
- {CLAIM_3}

---

## 2) 问题定义与 Challenge 分析

**问题的正式定义：**
{FORMAL_PROBLEM_STATEMENT}

**作者列举的 Challenges：**

| # | Challenge | 根因 | 对应的系统模块 |
|---|-----------|------|----------------|
| C1 | {challenge} | {root cause} | {module} |
| C2 | ... | ... | ... |

根因分类（选择适用的）：
- [ ] 物理约束（信号、硬件、能量）
- [ ] 系统约束（延迟、内存、算力）
- [ ] 数据约束（标注、分布、泛化）
- [ ] 场景约束（用户行为、环境变化）

---

## 3) 系统设计与架构

**Overview（用文字重现 Figure 1 或架构图）：**
{ARCHITECTURE_DESCRIPTION}

**各模块拆解：**

### {MODULE_NAME_1}
- 功能：{FUNCTION}
- 解决的 Challenge：{WHICH_CHALLENGE}
- 关键设计决策：{DESIGN_DECISION}
- 为什么这样而不是另一个方案：{RATIONALE}

### {MODULE_NAME_2}
（重复上述结构）

**关键 Trade-off 记录：**

| 决策点 | 选择了 | 放弃了 | 原因 |
|--------|--------|--------|------|
| {decision} | {chosen} | {alternative} | {why} |

这一节是 IoT/Systems 论文精读的核心。每个 trade-off 都应有明确的 rationale，
而不只是描述系统做了什么。

---

## 4) 实现细节

**硬件平台：**
{HARDWARE}

**软件栈：**
{SOFTWARE_STACK}

**工程约束（填写适用的）：**
- 延迟 budget：{LATENCY}
- 功耗限制：{POWER}
- 内存限制：{MEMORY}
- 采样率 / 精度：{SAMPLING}

**值得记录的 engineering tricks：**
- {TRICK_1}
- {TRICK_2}

如果全文不可访问，此节写"实现细节不可获取，仅分析摘要和图表"。

---

## 5) 实验与评估

**Baselines：**

| Baseline | 是否公平 | 备注 |
|----------|----------|------|
| {baseline_name} | 是 / 存疑 | {note} |

评估 baseline 是否公平：是否有明显更强的对比系统被遗漏？

**核心 Metrics 及选择理由：**
{METRIC_RATIONALE}

**实验场景覆盖：**
- [ ] lab/controlled setting
- [ ] in-the-wild / real users
- [ ] edge cases / failure modes tested

**最强结果：**
{BEST_RESULT}

**最弱结果 / 明显局限：**
{WEAKEST_RESULT}

**如果让我设计实验，我会额外测试：**
{ADDITIONAL_EXPERIMENTS}

---

## 6) Related Work 定位

> 利用已有的 papers.json，将这篇与已读论文对比。

**与已知工作的对比：**

| 已读论文 | 与本文关系 | 本文的 novelty 边界 |
|----------|------------|---------------------|
| {paper_alias} | {relation} | {novelty_claim} |

**本文在领域时间线中的位置：**
{TIMELINE_POSITION}

（参考 conference-scout 生成的 timeline_role：这篇更像 foundation / consolidation / frontier？）

**有没有作者未引用但应该讨论的工作：**
{MISSING_RELATED_WORK}

---

## 7) 个人 Synthesis

**最值得借鉴的一个 idea：**
{TOP_IDEA}

**最让我存疑的一个假设：**
{QUESTIONABLE_ASSUMPTION}

**如果我来做下一步，我会：**
{NEXT_STEPS}

**与我自己研究的连接点：**
{PERSONAL_CONNECTION}

---

## 8) 评分

评分维度：
- **论文质量（0–2）**：问题重要性、方法严谨性、实验充分性
- **个人收获（0–2）**：对我的研究方向有多大启发
- **Base**：1

Total = 1 + 质量分 + 收获分，满分 5。

质量分：{Q}/2 — {Q_REASON}
收获分：{O}/2 — {O_REASON}
**Total: {TOTAL}/5**
```

---

## Paper Type Adaptation

The depth of each section varies by paper type. Adjust emphasis accordingly:

**Systems / IoT paper** (MobiCom, SenSys, IMWUT, MobiSys):
- Section 3 (Architecture) and Section 4 (Implementation) should be the most detailed
- Section 2 (Challenges) should map each challenge to a concrete system component
- Section 5 (Evaluation) should scrutinize whether real-world conditions were tested

**Algorithm / ML paper** (NeurIPS, ICLR, CVPR):
- Section 3 should focus on the model architecture and the key loss / training trick
- Section 4 can be brief (dataset, framework, compute budget)
- Section 5 should focus on ablations and what each component contributes

**Measurement / Empirical paper** (IMC, UbiComp measurement tracks):
- Section 2 should capture the measurement methodology and dataset scope
- Section 3 is not about system design but about analysis methodology
- Section 5 should record the most surprising empirical finding

**Survey paper**:
- Replace Sections 2–4 with a taxonomy summary
- Section 6 becomes the primary output: how does this survey periodize the field?

---

## Match Existing State

Load `output/papers.json` and find the paper by:
1. exact `url`
2. matching `arxiv_id`
3. normalized title match only as a last resort

If absent, create a new entry during the save step.

---

## Persistent State Update

### `output/papers.json`

If the paper already exists:
- set `status` to `"reading"`
- set `note_path` to the saved note file
- update `last_updated`
- set `pdf_url` if a reliable direct PDF link is available
- set `paper_type` to one of `systems`, `algorithm`, `measurement`, `survey`

If the paper does not exist:
- create a new entry with all available metadata
- set `status` to `"reading"`
- set `note_path`, `tags`, `paper_type`

### `output/kanban.html`

Load from `assets/kanban.html`. Regenerate with updated paper state.

---

## Response Format

```
精读完成 — {ALIAS}
{FULL_TITLE}
{AUTHORS} | {VENUE} {YEAR} | {TOTAL}/5

Paper type: {PAPER_TYPE}

Vision:      {ONE_LINE_VISION}
Top result:  {BEST_RESULT}
Key insight: {TOP_IDEA}
Top concern: {QUESTIONABLE_ASSUMPTION}

Challenges:  {N} identified, all mapped to system modules
Trade-offs:  {N} recorded with rationale

Notes: output/notes/{TOPIC_SLUG}/{PAPER_ID}.md
Dashboard: output/kanban.html
```

---

## Error Handling

| Error | Action |
|---|---|
| arXiv HTML unavailable | continue with abstract; mark Sections 3 and 4 as "不可获取" |
| non-arXiv paper lacks full text | use abstract + metadata; state limitation explicitly |
| paper absent from papers.json | create new entry |
| malformed papers.json | recreate carefully and warn |
| no figures available | omit figure references; do not fabricate |
| paper is very long (>15 pages) | prioritize Sections 1, 2, 3, 5; note that Section 4 may be incomplete |