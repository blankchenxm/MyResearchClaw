# MyResearchClaw

A Claude Code agent system for searching and tracking academic papers from top venues.

## What it does

Two skills power this system:

**`/conference-scout`** — searches Semantic Scholar, DBLP, and arXiv for papers from top conferences by topic and year range. Results accumulate in a persistent kanban board.

**`/paper-reader`** — deep-reads a single paper (arXiv or DOI) and generates structured DNL (Deep Note & List) reading notes. Updates the kanban to move the paper into the "Reading" column.

## Kanban board

`output/kanban.html` — a dark-themed kanban with three columns: **To Read / Reading / Done**. Generated from `output/papers.json` and overwritten on every operation. Open in any browser.

`output/papers.json` — persistent data store. Papers accumulate across searches; status transitions from `unread` → `reading` → `done`.

`output/notes/` — DNL reading notes saved as markdown files (one per paper).

## Supported venue groups

| Group | Conferences |
|-------|-------------|
| `ai_ml` | NeurIPS, ICLR, ICML, AAAI, CVPR, ACL, EMNLP |
| `iot_systems` | MobiCom, MobiSys, SenSys, UbiComp/IMWUT, IPSN |
| `networking` | SIGCOMM, NSDI, INFOCOM |
| `systems` | OSDI, SOSP, ATC, EuroSys |
| `security` | USENIX Security, CCS, IEEE S&P, NDSS |
| `hci` | CHI, UIST, CSCW |

## Usage

### Search papers

```
/conference-scout
帮我搜索 wearable audio privacy 在 IoT 顶会 2022-2025 年的论文
```

Prompts: `搜论文`, `find papers`, `顶会论文`, `[topic] papers in [conference]`

### Deep-read a paper

Click the **Read Paper** button on any kanban card — it shows the command to paste:

```
/paper-reader https://arxiv.org/abs/2401.XXXXX
/paper-reader https://doi.org/10.1145/XXXXXXX
```

The skill fetches the paper, generates a DNL note in `output/notes/`, updates `papers.json`, and regenerates the kanban.

## Data sources

1. **Semantic Scholar API** — primary; venue + citation metadata
2. **DBLP API** — fallback when SS is rate-limited; reliable, no rate limit
3. **arXiv Atom/XML API** — supplementary recent preprints

## Project structure

```
.claude/
  settings.local.json          # domain permissions
  skills/
    conference-scout/
      SKILL.md                 # search skill definition
      templates/kanban.html    # kanban HTML template
    paper-reader/
      SKILL.md                 # deep reading skill definition
output/
  papers.json                  # persistent paper database
  kanban.html                  # generated kanban board
  notes/                       # DNL reading notes (markdown)
```
