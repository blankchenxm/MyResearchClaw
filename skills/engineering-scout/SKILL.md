---
name: engineering-scout
description: >
  Search engineering implementations for a research topic across GitHub, products, and news, then
  generate an engineering-focused HTML page. Use when the user wants to know whether a topic has
  open-source implementations, commercial products, or real-world deployment signals.
---

# Engineering Scout

Goal: for a research topic, collect implementation-oriented evidence and generate `output/engineering.html`.

## Inputs

Extract:

| Field | Description | Default |
|---|---|---|
| `topic` | engineering topic or the same topic used in conference-scout | required |
| `year_start` | start year for news / product recency | `2022` |
| `year_end` | end year for news / product recency | current year |
| `focus` | optional filters such as `github`, `products`, `news` | all |
| `output_html` | optional standalone HTML output path when the user wants a topic-specific engineering page without overwriting the shared engineering page | optional |

If the user asks this immediately after a paper search, reuse the latest paper-search topic unless the user overrides it.

## Search Scope

You must cover all three areas unless the user explicitly narrows scope:

1. GitHub open-source repositories and implementation projects
2. Real products, product features, deployed systems, or startups related to the topic
3. News, launch posts, technical blogs, or real-world adoption signals

## Source Priority

1. Official product pages / company engineering blogs
2. GitHub repositories and project documentation
3. Primary launch posts, reputable news, or company announcements
4. Supporting metadata sources only when needed

## Output Requirements

For each meaningful result, extract:

- title
- category: `open_source`, `product`, `news`
- organization / company / maintainer
- year or date
- URL
- concise implementation summary
- why it matters for the topic

Additional requirements:

- for products, explain how the implementation likely works using available technical clues
- for GitHub projects, summarize stack, architecture, deployment pattern, and maturity when visible
- for news, connect the story back to real engineering feasibility rather than just repeating headlines

## HTML Output

Write a single generated page to:

```text
output/engineering.html
```

Load the template from:

```text
assets/engineering.html
```

If the user explicitly asks for standalone topic-specific output that must not overwrite existing results:

- generate a dedicated engineering page such as `output/projects/{topic_slug}/engineering.html`
- keep the shared `output/engineering.html` unchanged unless the task explicitly requests updating it

Fill:

- `{{TOPIC}}`
- `{{YEAR_RANGE}}`
- `{{LAST_UPDATED}}`
- `{{OPEN_SOURCE_COUNT}}`
- `{{PRODUCT_COUNT}}`
- `{{NEWS_COUNT}}`
- `{{OPEN_SOURCE_ITEMS}}`
- `{{PRODUCT_ITEMS}}`
- `{{NEWS_ITEMS}}`
- `{{KEY_TAKEAWAYS}}`

## Page Logic

- this page is separate from `output/kanban.html`
- the paper page should remain focused on papers
- users can navigate from the paper page to the engineering page

## Response Format

Reply with a compact summary:

```text
Engineering Scout — {TOPIC}
Open source: {N}
Products: {M}
News / deployment signals: {K}

Key takeaway: {ONE_SENTENCE}

Engineering page: output/engineering.html
```

## Error Handling

| Error | Handling |
|---|---|
| weak GitHub coverage | say that implementation is sparse and shift emphasis to product/news evidence |
| no clear products | explain that the topic is still mostly research-stage |
| marketing-heavy sources | extract only defensible technical claims |
