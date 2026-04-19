#!/usr/bin/env python3
"""
MyResearchClaw local API server.

Usage:
  cd /home/meng/Agent/MyResearchClaw
  python serve.py

Then open http://localhost:5678/kanban.html

Optional environment variables:
  MYRESEARCHCLAW_MODEL      default: gpt-5.4-mini
  MYRESEARCHCLAW_CODEX_BIN  default: codex
"""
import json
import os
import re
import select
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
import urllib.request
import urllib.error
import time
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 5678
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "output")
PAPERS_JSON = os.path.join(OUTPUT_DIR, "papers.json")
NOTES_DIR = os.path.join(OUTPUT_DIR, "notes")
PDFS_DIR = os.path.join(OUTPUT_DIR, "pdfs")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
ENGINEERING_STATUS_JSON = os.path.join(OUTPUT_DIR, "engineering_status.json")
SKILLS_DIR = os.path.join(ROOT, "skills")
KANBAN_TEMPLATE = os.path.join(SKILLS_DIR, "conference-scout", "assets", "kanban.html")
KANBAN_HTML = os.path.join(OUTPUT_DIR, "kanban.html")
ENGINEERING_TEMPLATE = os.path.join(SKILLS_DIR, "engineering-scout", "assets", "engineering.html")
ENGINEERING_HTML = os.path.join(OUTPUT_DIR, "engineering.html")

MODEL = os.environ.get("MYRESEARCHCLAW_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
CODEX_BIN = os.environ.get("MYRESEARCHCLAW_CODEX_BIN", "codex").strip() or "codex"


def resolve_codex_bin():
    if os.path.isabs(CODEX_BIN) and os.path.exists(CODEX_BIN):
        return CODEX_BIN
    resolved = shutil.which(CODEX_BIN)
    if resolved:
        return resolved
    fallback = "/home/wangmingke/.nvm/versions/node/v24.14.1/bin/codex"
    if os.path.exists(fallback):
        return fallback
    return CODEX_BIN


RESOLVED_CODEX_BIN = resolve_codex_bin()


def load_papers():
    with open(PAPERS_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_papers(data):
    with open(PAPERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def today_iso():
    return datetime.now().strftime("%Y-%m-%d")


def set_paper_fields(paper_id, **kwargs):
    data = load_papers()
    for paper in data["papers"]:
        if paper["id"] == paper_id:
            paper.update(kwargs)
            break
    save_papers(data)


def load_kanban_template():
    with open(KANBAN_TEMPLATE, encoding="utf-8") as f:
        return f.read()


def load_engineering_template():
    with open(ENGINEERING_TEMPLATE, encoding="utf-8") as f:
        return f.read()


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def citation_badge(citations):
    if citations in (None, ""):
        return "cite-none", "★ —"
    try:
        citations = int(citations)
    except (TypeError, ValueError):
        return "cite-none", f"★ {escape(str(citations))}"
    if citations >= 100:
        return "cite-high", f"★ {citations}"
    if citations >= 10:
        return "cite-mid", f"★ {citations}"
    if citations > 0:
        return "cite-low", f"★ {citations}"
    return "cite-none", "★ 0"


def venue_badge(paper):
    venue = (paper.get("venue") or "Unknown").strip()
    year = paper.get("year")
    label = f"{venue} {year}".strip()
    klass = "venue-badge arxiv" if paper.get("is_arxiv") else "venue-badge"
    return klass, label


def status_card_class(paper):
    status = (paper.get("status") or "").strip()
    if status == "done":
        return "paper-card is-done"
    if status == "reading" or (paper.get("progress") or 0) > 0:
        return "paper-card is-reading"
    if paper.get("is_arxiv"):
        return "paper-card is-arxiv"
    return "paper-card is-confirmed"


def render_tags(tags):
    classes = ["tag-cyan", "tag-purple", "tag-pink"]
    rendered = []
    for idx, tag in enumerate((tags or [])[:3]):
        rendered.append(
            f'<span class="card-tag {classes[idx % len(classes)]}">{escape(str(tag))}</span>'
        )
    return "\n          ".join(rendered)


def render_progress_state(paper):
    progress = int(paper.get("progress") or 0)
    status = (paper.get("status") or "").strip()
    note_path = paper.get("note_path")

    fill_class = "progress-fill"
    label_class = "progress-label"
    label_text = ""

    if status == "done" or progress >= 100:
        fill_class += " done"
        label_class += " done"
        label_text = "✓ Complete"
    elif progress > 0 or status == "reading":
        fill_class += " active"
        label_text = f"Reading... {progress}%"

    if status == "done":
        button_html = (
            f'<button data-role="read-btn" class="btn btn-done" onclick="navigateTo(\'notes\', \'{escape_js(paper["id"])}\')">'
            "✅ Done"
            "</button>"
        )
    elif note_path and os.path.exists(os.path.join(ROOT, note_path)):
        button_html = (
            f'<button data-role="read-btn" class="btn btn-notes" onclick="navigateTo(\'notes\', \'{escape_js(paper["id"])}\')">'
            "📄 View Notes"
            "</button>"
        )
    elif progress > 0 or status == "reading":
        button_html = '<button data-role="read-btn" class="btn btn-read reading" disabled>⏳ Reading...</button>'
    else:
        button_html = (
            '<button data-role="read-btn" class="btn btn-read" '
            f'onclick="triggerRead(\'{escape_js(paper["id"])}\','
            f'\'{escape_js(paper.get("url") or "")}\','
            f'\'{escape_js(paper.get("title") or "")}\')">📖 Read Paper</button>'
        )

    return progress, fill_class, label_class, label_text, button_html


def escape_js(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def infer_pdf_url(paper):
    local_relpath = paper.get("pdf_local_path")
    if local_relpath and os.path.exists(os.path.join(ROOT, local_relpath)):
        return f"/api/pdf/{urllib.parse.quote(paper['id'])}"

    pdf_url = (paper.get("pdf_url") or "").strip()
    if pdf_url:
        return pdf_url

    paper_url = (paper.get("url") or "").strip()
    if "arxiv.org/abs/" in paper_url:
        return paper_url.replace("/abs/", "/pdf/") + ".pdf"
    if "arxiv.org/pdf/" in paper_url:
        return paper_url if paper_url.endswith(".pdf") else f"{paper_url}.pdf"

    note_path = paper.get("note_path")
    if note_path:
        note_abspath = os.path.join(ROOT, note_path)
        if os.path.exists(note_abspath):
            try:
                with open(note_abspath, encoding="utf-8") as f:
                    note_md = f.read()
                match = re.search(r"-\s*(?:\*\*)?(?:PDF|PDF mirror)(?::(?:\*\*)?)?\s*(https?://\S+)", note_md, re.I)
                if match:
                    return match.group(1)
            except OSError:
                pass
    return ""


def paper_pdf_relpath_for_paper(paper):
    return f"output/pdfs/{paper_topic_slug(paper)}/{paper['id']}.pdf"


def paper_pdf_abspath_for_paper(paper):
    return os.path.join(ROOT, paper_pdf_relpath_for_paper(paper))


def local_pdf_api_path(paper_id):
    return f"/api/pdf/{urllib.parse.quote(paper_id)}"


def update_paper_metadata(paper_id, **kwargs):
    data = load_papers()
    updated = False
    for paper in data.get("papers", []):
        if paper.get("id") == paper_id:
            paper.update(kwargs)
            updated = True
            break
    if updated:
        data["last_updated"] = today_iso()
        save_papers(data)
    return updated


def fetch_url(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 MyResearchClaw/1.0",
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
    return body, content_type, final_url


def fetch_json(url, timeout=20):
    body, _, _ = fetch_url(url, timeout=timeout)
    return json.loads(body.decode("utf-8", errors="ignore"))


def looks_like_pdf(data):
    return data.lstrip()[:4] == b"%PDF"


def extract_pdf_candidates_from_html(html, base_url):
    candidates = []
    patterns = [
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+\.pdf[^"\']*)["\']',
        r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'href=["\']([^"\']+/doi/pdf/[^"\']+)["\']',
        r'href=["\']([^"\']+/pdf/[^"\']+)["\']',
        r'href=["\']([^"\']+arxiv\.org/abs/[^"\']+)["\']',
        r'href=["\']([^"\']+openreview\.net/pdf\?id=[^"\']+)["\']',
        r'href=["\']([^"\']+openreview\.net/forum\?id=[^"\']+)["\']',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html, re.I):
            candidate = urllib.parse.urljoin(base_url, match.replace("&amp;", "&"))
            if candidate not in candidates:
                candidates.append(candidate)

    if "dl.acm.org/doi/" in base_url and "/pdf/" not in base_url:
        candidates.append(base_url.replace("/doi/", "/doi/pdf/"))
    return candidates


def collect_pdf_candidates(paper):
    candidates = []

    def add(url):
        if not url:
            return
        url = url.strip()
        if not url or url in candidates:
            return
        candidates.append(url)

    add(paper.get("pdf_source_url"))
    pdf_url = (paper.get("pdf_url") or "").strip()
    if pdf_url.startswith("http://") or pdf_url.startswith("https://"):
        add(pdf_url)

    paper_url = (paper.get("url") or "").strip()
    if paper_url:
        add(paper_url)
        if "arxiv.org/abs/" in paper_url:
            add(paper_url.replace("/abs/", "/pdf/") + ".pdf")
        if "arxiv.org/pdf/" in paper_url:
            add(paper_url if paper_url.endswith(".pdf") else f"{paper_url}.pdf")

    note_path = paper.get("note_path")
    if note_path:
        note_abspath = os.path.join(ROOT, note_path)
        if os.path.exists(note_abspath):
            try:
                with open(note_abspath, encoding="utf-8") as f:
                    note_md = f.read()
                for match in re.findall(r"-\s*(?:\*\*)?(?:PDF|PDF mirror)(?::(?:\*\*)?)?\s*(https?://\S+)", note_md, re.I):
                    add(match)
            except OSError:
                pass

    expanded = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.startswith("http://") or candidate.startswith("https://"):
            if "arxiv.org/abs/" in candidate:
                add(candidate.replace("/abs/", "/pdf/") + ".pdf")
                continue
            if "openreview.net/forum?id=" in candidate:
                add(candidate.replace("/forum?id=", "/pdf?id="))
                continue
            if not re.search(r"\.pdf(?:$|\?)", candidate, re.I):
                try:
                    body, content_type, final_url = fetch_url(candidate, timeout=12)
                    if "pdf" in content_type.lower() or looks_like_pdf(body):
                        add(final_url)
                        continue
                    html = body.decode("utf-8", errors="ignore")
                    for extra in extract_pdf_candidates_from_html(html, final_url):
                        add(extra)
                except Exception:
                    pass

    title = (paper.get("title") or "").strip()
    if title:
        try:
            query = urllib.parse.quote(title)
            data = fetch_json(
                "https://api.semanticscholar.org/graph/v1/paper/search/match"
                f"?query={query}&fields=title,url,openAccessPdf,externalIds",
                timeout=12,
            )
            open_pdf = ((data or {}).get("openAccessPdf") or {}).get("url")
            add(open_pdf)
            matched_url = (data or {}).get("url")
            add(matched_url)
            arxiv_id = ((data or {}).get("externalIds") or {}).get("ArXiv")
            if arxiv_id:
                add(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
        except Exception:
            pass
    return candidates


def ensure_local_pdf(paper_id):
    paper = find_paper_by_id(paper_id)
    if not paper:
        return ""

    local_relpath = paper.get("pdf_local_path") or paper_pdf_relpath_for_paper(paper)
    local_abspath = os.path.join(ROOT, local_relpath)
    if os.path.exists(local_abspath) and os.path.getsize(local_abspath) > 0:
        if paper.get("pdf_local_path") != local_relpath:
            update_paper_metadata(paper_id, pdf_local_path=local_relpath)
        return local_abspath

    os.makedirs(os.path.dirname(local_abspath), exist_ok=True)
    candidates = collect_pdf_candidates(paper)

    for candidate in candidates:
        try:
            body, content_type, final_url = fetch_url(candidate)
            if not ("pdf" in content_type.lower() or looks_like_pdf(body)):
                continue
            tmp_path = local_abspath + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(body)
            os.replace(tmp_path, local_abspath)
            update_paper_metadata(
                paper_id,
                pdf_local_path=local_relpath,
                pdf_source_url=final_url,
                pdf_url=paper.get("pdf_url") or final_url,
            )
            return local_abspath
        except Exception:
            continue
    return ""


def render_paper_card(idx, paper):
    citations_class, citations_text = citation_badge(paper.get("citations"))
    venue_class, venue_text = venue_badge(paper)
    progress, fill_class, label_class, label_text, button_html = render_progress_state(paper)
    tags_html = render_tags(paper.get("tags"))
    summary_en = escape(paper.get("summary_en") or "")
    summary_zh = escape(paper.get("summary_zh") or "")
    paper_url = escape(paper.get("url") or "")
    pdf_url = escape(infer_pdf_url(paper))
    title = escape(paper.get("title") or "Untitled")
    authors = escape(paper.get("authors") or "Unknown authors")

    tags_block = f"\n          {tags_html}" if tags_html else ""

    return f"""
      <!-- ── Paper {idx} ── -->
      <div class="{status_card_class(paper)}" data-id="{escape(paper["id"])}" data-url="{paper_url}" data-pdf-url="{pdf_url}" data-progress="{progress}">
        <div class="card-header">
          <div class="card-title"><a href="{paper_url}" target="_blank">{title}</a></div>
          <span class="citations {citations_class}">{citations_text}</span>
        </div>
        <div class="card-authors">{authors}</div>
        <div class="card-meta">
          <span class="{venue_class}">{escape(venue_text)}</span>{tags_block}
        </div>
        <div class="summary-block">
          <div class="summary-label">EN</div>
          <div class="summary-en">{summary_en}</div>
          <div class="summary-label" style="margin-top:6px;">中文</div>
          <div class="summary-zh">{summary_zh}</div>
        </div>
        <div class="progress-row">
          <div class="progress-track"><div class="{fill_class}" style="width:{progress}%"></div></div>
          <span class="{label_class}">{escape(label_text)}</span>
        </div>
        <div class="card-actions">
          <a href="{paper_url}" target="_blank" class="btn btn-view">🔗 View Paper</a>
          {button_html}
        </div>
      </div>"""


def render_dashboard_html(active_topic, active_year_range, active_venues, engineering_link, papers):
    template = load_kanban_template()
    all_papers = "\n".join(
        render_paper_card(idx, paper) for idx, paper in enumerate(papers, start=1)
    )
    return (
        template.replace("{{LAST_UPDATED}}", escape(today_iso()))
        .replace("{{ACTIVE_TOPIC}}", escape(active_topic))
        .replace("{{ACTIVE_YEAR_RANGE}}", escape(active_year_range))
        .replace("{{ACTIVE_VENUES}}", escape(active_venues))
        .replace("{{ENGINEERING_LINK}}", engineering_link)
        .replace("{{ALL_PAPERS}}", all_papers)
    )


def render_topic_index_html(searches, papers):
    topic_rows = []
    seen = set()
    for search in reversed(searches):
        topic = search.get("topic") or "Research Topic"
        if topic in seen:
            continue
        seen.add(topic)
        slug = slugify_topic(topic)
        paper_count = sum(1 for paper in papers if paper.get("topic") == topic)
        topic_rows.append(
            {
                "topic": topic,
                "slug": slug,
                "paper_count": paper_count,
                "year_range": search.get("year_range") or "Unknown Range",
                "venues": search.get("venues") or "Unknown Venues",
                "date": search.get("date") or today_iso(),
            }
        )

    cards_html = "\n".join(
        f"""
        <article class="topic-card">
          <div class="topic-top">
            <div>
              <div class="topic-eyebrow">Research Theme</div>
              <h2>{escape(row["topic"])}</h2>
            </div>
            <div class="topic-count">{row["paper_count"]} papers</div>
          </div>
          <div class="topic-meta">
            <span>{escape(row["year_range"])}</span>
            <span>{escape(row["date"])}</span>
          </div>
          <p class="topic-venues">{escape(row["venues"])}</p>
          <div class="topic-actions">
            <a href="/{row["slug"]}-papers.html">Open Papers →</a>
            <a href="/{row["slug"]}-engineering.html">Engineering View →</a>
          </div>
        </article>"""
        for row in topic_rows
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MyResearchClaw</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
:root {{
  --bg:#0c1118; --panel:#151c27; --panel-soft:#101722; --text:#edf3ff; --dim:#93a6c3;
  --muted:#6c7a90; --line:rgba(255,255,255,0.08); --blue:#69a6ff; --cyan:#38d9c7; --amber:#ffd66e;
}}
body {{
  font-family:'Noto Sans SC',sans-serif; min-height:100vh; color:var(--text);
  background:radial-gradient(circle at top right, rgba(105,166,255,0.14), transparent 24%),
             radial-gradient(circle at top left, rgba(56,217,199,0.08), transparent 20%),
             var(--bg);
}}
body.light {{
  --bg:#f4f7fb; --panel:#ffffff; --panel-soft:#edf2f8; --text:#18202c; --dim:#506176;
  --muted:#68778b; --line:rgba(15,23,42,0.10); --blue:#2364d2; --cyan:#0f9f90; --amber:#b98911;
}}
.wrap {{ max-width:1320px; margin:0 auto; padding:28px 28px 80px; }}
.theme-toggle {{
  position:fixed; top:16px; right:16px; z-index:9999; width:40px; height:40px; border-radius:50%;
  border:1px solid var(--line); background:var(--panel); color:var(--text); cursor:pointer; font-size:16px;
}}
.hero {{
  border:1px solid var(--line); border-radius:28px; padding:30px 32px;
  background:linear-gradient(145deg, rgba(105,166,255,0.14), rgba(56,217,199,0.04));
  margin-bottom:24px;
}}
.hero-eyebrow {{ font:600 12px 'JetBrains Mono', monospace; color:var(--amber); text-transform:uppercase; letter-spacing:.14em; margin-bottom:12px; }}
.hero h1 {{ font-size:48px; line-height:1.04; font-weight:900; max-width:980px; }}
.hero p {{ margin-top:14px; color:var(--dim); font-size:15px; line-height:1.85; max-width:900px; }}
.topics {{ display:grid; gap:18px; }}
.topic-card {{ background:var(--panel); border:1px solid var(--line); border-radius:22px; padding:22px 24px; }}
.topic-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:12px; }}
.topic-eyebrow {{ font:600 11px 'JetBrains Mono', monospace; color:var(--cyan); text-transform:uppercase; letter-spacing:.12em; margin-bottom:8px; }}
.topic-card h2 {{ font-size:26px; line-height:1.28; font-weight:900; }}
.topic-count {{ white-space:nowrap; border:1px solid var(--line); border-radius:999px; padding:6px 10px; font:600 11px 'JetBrains Mono', monospace; color:var(--blue); }}
.topic-meta {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; color:var(--muted); font:500 11px 'JetBrains Mono', monospace; }}
.topic-venues {{ color:var(--dim); line-height:1.8; margin-bottom:16px; }}
.topic-actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
.topic-actions a {{
  display:inline-flex; align-items:center; gap:6px; text-decoration:none; border:1px solid var(--line);
  border-radius:999px; padding:10px 14px; font-size:13px; color:var(--text); background:rgba(255,255,255,0.04);
}}
.topic-actions a:last-child {{ color:var(--cyan); border-color:rgba(56,217,199,0.18); background:rgba(56,217,199,0.08); }}
@media (max-width: 720px) {{
  .wrap {{ padding:16px 16px 60px; }}
  .hero {{ padding:22px 20px; }}
  .hero h1 {{ font-size:30px; }}
  .topic-top {{ flex-direction:column; }}
}}
</style>
</head>
<body>
  <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>
  <div class="wrap">
    <section class="hero">
      <div class="hero-eyebrow">MyResearchClaw</div>
      <h1>Topic Navigator</h1>
      <p>当前仅保留两个主题。先从对应的 Papers 页面进入，再在页面顶部点击 Engineering View；后续精读笔记会按主题写入 <code>output/notes/&lt;topic-slug&gt;/</code>。</p>
    </section>
    <section class="topics">
      {cards_html}
    </section>
  </div>
<script>
function applyTheme() {{
  const light = localStorage.getItem('theme') === 'light';
  document.body.classList.toggle('light', light);
  document.querySelector('.theme-toggle').textContent = light ? '☀️' : '🌙';
}}
function toggleTheme() {{
  const light = !document.body.classList.contains('light');
  localStorage.setItem('theme', light ? 'light' : 'dark');
  applyTheme();
}}
window.addEventListener('load', applyTheme);
</script>
</body>
</html>"""


def regenerate_kanban():
    data = load_papers()
    papers = data.get("papers", [])
    searches = data.get("searches", [])
    topics = [search.get("topic") for search in searches if search.get("topic")]
    if len(set(topics)) > 1:
        rendered = render_topic_index_html(searches, papers)
        with open(KANBAN_HTML, "w", encoding="utf-8") as f:
            f.write(rendered)
        return

    latest_search = searches[-1] if searches else {}
    active_topic = latest_search.get("topic") or "Research Topic"
    active_year_range = latest_search.get("year_range") or "Unknown Range"
    active_venues = latest_search.get("venues") or "Unknown Venues"
    active_papers = [paper for paper in papers if paper.get("topic") == active_topic] or papers
    rendered = render_dashboard_html(
        active_topic=active_topic,
        active_year_range=active_year_range,
        active_venues=active_venues,
        engineering_link="/engineering.html",
        papers=active_papers,
    )

    with open(KANBAN_HTML, "w", encoding="utf-8") as f:
        f.write(rendered)


def slugify_topic(topic):
    topic = topic.lower()
    topic = re.sub(r"[^a-z0-9]+", "-", topic)
    topic = re.sub(r"-+", "-", topic).strip("-")
    return topic or "topic"


def paper_topic_slug(paper):
    return slugify_topic(paper.get("topic") or "unclassified")


def find_paper_by_id(paper_id):
    data = load_papers()
    for paper in data.get("papers", []):
        if paper.get("id") == paper_id:
            return paper
    return None


def write_topic_dashboard(topic, year_range, venues):
    data = load_papers()
    topic_papers = [paper for paper in data.get("papers", []) if paper.get("topic") == topic]
    slug = slugify_topic(topic)
    papers_name = f"{slug}-papers.html"
    engineering_name = f"{slug}-engineering.html"
    papers_html = render_dashboard_html(
        active_topic=topic,
        active_year_range=year_range,
        active_venues=venues,
        engineering_link=f"/{engineering_name}",
        papers=topic_papers,
    )
    with open(os.path.join(OUTPUT_DIR, papers_name), "w", encoding="utf-8") as f:
        f.write(papers_html)
    return papers_name, engineering_name


def ensure_engineering_page():
    data = load_papers()
    searches = data.get("searches", [])
    latest_search = searches[-1] if searches else {}
    topic = latest_search.get("topic") or "Engineering Topic"
    year_range = latest_search.get("year_range") or "2022-current"
    template = load_engineering_template()
    placeholder = (
        '<div class="takeaway">Engineering scout page has not been generated yet. '
        'Run `engineering-scout` for this topic to populate GitHub projects, products, and deployment signals.</div>'
    )
    html = (
        template.replace("{{TOPIC}}", escape(topic))
        .replace("{{YEAR_RANGE}}", escape(year_range))
        .replace("{{LAST_UPDATED}}", escape(data.get("last_updated") or today_iso()))
        .replace("{{OPEN_SOURCE_COUNT}}", "0")
        .replace("{{PRODUCT_COUNT}}", "0")
        .replace("{{NEWS_COUNT}}", "0")
        .replace("{{KEY_TAKEAWAYS}}", placeholder)
        .replace("{{OPEN_SOURCE_ITEMS}}", '<div class="item"><div class="summary">No engineering results generated yet.</div></div>')
        .replace("{{PRODUCT_ITEMS}}", '<div class="item"><div class="summary">No product results generated yet.</div></div>')
        .replace("{{NEWS_ITEMS}}", '<div class="item"><div class="summary">No news or deployment signals generated yet.</div></div>')
    )
    with open(ENGINEERING_HTML, "w", encoding="utf-8") as f:
        f.write(html)


def load_engineering_status():
    return load_json_file(
        ENGINEERING_STATUS_JSON,
        {
            "topic": "",
            "status": "idle",
            "message": "",
            "last_updated": "",
            "page_ready": os.path.exists(ENGINEERING_HTML),
        },
    )


def save_engineering_status(**kwargs):
    current = load_engineering_status()
    current.update(kwargs)
    if "page_ready" not in kwargs:
        current["page_ready"] = os.path.exists(ENGINEERING_HTML)
    save_json_file(ENGINEERING_STATUS_JSON, current)


def latest_search_context():
    data = load_papers()
    searches = data.get("searches", [])
    latest_search = searches[-1] if searches else {}
    return {
        "topic": latest_search.get("topic") or "Engineering Topic",
        "year_range": latest_search.get("year_range") or "2022-current",
        "venues": latest_search.get("venues") or "",
        "date": latest_search.get("date") or today_iso(),
    }


def build_engineering_prompt(topic, year_range, venues):
    return f"""Use the project skill `engineering-scout` to investigate the same research topic from the engineering side.

Topic: {topic}
Year range: {year_range}
Related paper venues: {venues}

Required outcomes:
- Search GitHub open-source implementations
- Search real products or deployed features
- Search news, launch posts, and real-world engineering signals
- Generate output/engineering.html
- Write concrete implementation details, not generic summaries
"""


def generate_engineering_bg(topic, year_range, venues):
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, "engineering.log")
    save_engineering_status(
        topic=topic,
        status="running",
        message="Engineering scout is gathering GitHub projects, products, and deployment signals.",
        last_updated=today_iso(),
        page_ready=os.path.exists(ENGINEERING_HTML),
    )

    prompt = build_engineering_prompt(topic, year_range, venues)
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".txt", delete=False) as output_file:
        output_path = output_file.name

    cmd = [
        RESOLVED_CODEX_BIN,
        "exec",
        "--cd",
        ROOT,
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "--output-last-message",
        output_path,
        "--color",
        "never",
        "--search",
        "-m",
        MODEL,
        prompt,
    ]

    try:
        codex_dir = os.path.dirname(RESOLVED_CODEX_BIN)
        env = os.environ.copy()
        env["PATH"] = codex_dir + os.pathsep + env.get("PATH", "")
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n"
                f"Topic: {topic}\nYear range: {year_range}\nVenues: {venues}\n"
                f"Command: {' '.join(cmd)}\n\n"
            )
            log_file.flush()

            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            logs = []
            last_output_at = time.time()
            while proc.poll() is None:
                if proc.stdout:
                    ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if ready:
                        line = proc.stdout.readline()
                        if line:
                            stripped = line.rstrip()
                            log_file.write(stripped + "\n")
                            log_file.flush()
                            logs.append(stripped)
                            logs = logs[-80:]
                            last_output_at = time.time()
                if os.path.exists(ENGINEERING_HTML) and time.time() - last_output_at >= 20:
                    log_file.write("[serve.py] Engineering page exists and Codex CLI is idle; terminating process.\n")
                    log_file.flush()
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

            remainder = proc.stdout.read() if proc.stdout else ""
            if remainder:
                for raw_line in remainder.splitlines():
                    stripped = raw_line.rstrip()
                    log_file.write(stripped + "\n")
                    logs.append(stripped)
                log_file.flush()
                logs = logs[-80:]

            if proc.returncode not in (0, -15):
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"codex exited {proc.returncode}")

        if not os.path.exists(ENGINEERING_HTML):
            raise RuntimeError("engineering-scout completed but did not create output/engineering.html")

        save_engineering_status(
            topic=topic,
            status="ready",
            message="Engineering view is ready.",
            last_updated=today_iso(),
            page_ready=True,
        )
        print(f"[serve.py] Engineering complete: {topic}", flush=True)
    except Exception as exc:
        save_engineering_status(
            topic=topic,
            status="error",
            message=str(exc),
            last_updated=today_iso(),
            page_ready=os.path.exists(ENGINEERING_HTML),
        )
        print(f"[serve.py] Engineering CLI error: {exc}", flush=True)
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


def maybe_start_engineering_generation(force=False):
    context = latest_search_context()
    status = load_engineering_status()
    if not force:
        if status.get("status") == "running":
            return False
        if status.get("topic") == context["topic"] and status.get("status") == "ready" and os.path.exists(ENGINEERING_HTML):
            return False
    thread = threading.Thread(
        target=generate_engineering_bg,
        args=(context["topic"], context["year_range"], context["venues"]),
        daemon=True,
    )
    thread.start()
    return True


def paper_note_relpath_for_paper(paper):
    return f"output/notes/{paper_topic_slug(paper)}/{paper['id']}.md"


def paper_note_relpath(paper_id):
    paper = find_paper_by_id(paper_id)
    if not paper:
        return f"output/notes/unclassified/{paper_id}.md"
    return paper_note_relpath_for_paper(paper)


def paper_log_abspath(paper_id):
    return os.path.join(LOGS_DIR, f"{paper_id}.log")


def snapshot_paper_state(paper_id):
    data = load_papers()
    for paper in data.get("papers", []):
        if paper.get("id") == paper_id:
            return {
                "status": paper.get("status", "unread"),
                "progress": int(paper.get("progress") or 0),
                "note_path": paper.get("note_path"),
                "last_updated": paper.get("last_updated"),
            }
    return {
        "status": "unread",
        "progress": 0,
        "note_path": None,
        "last_updated": None,
    }


def restore_paper_state(paper_id, state):
    data = load_papers()
    for paper in data.get("papers", []):
        if paper.get("id") == paper_id:
            paper["status"] = state["status"]
            paper["progress"] = state["progress"]
            paper["note_path"] = state["note_path"]
            if state["last_updated"] is not None:
                paper["last_updated"] = state["last_updated"]
            elif "last_updated" in paper:
                paper.pop("last_updated", None)
            break
    save_papers(data)
    regenerate_kanban()


def finalize_read_result(paper_id):
    paper = find_paper_by_id(paper_id)
    if not paper:
        return False
    note_relpath = paper_note_relpath_for_paper(paper)
    note_abspath = os.path.join(ROOT, note_relpath)
    if not os.path.exists(note_abspath):
        return False

    data = load_papers()
    data["last_updated"] = today_iso()
    for paper in data.get("papers", []):
        if paper.get("id") == paper_id:
            paper.update(
                {
                    "progress": 100,
                    "status": "reading",
                    "note_path": note_relpath,
                    "last_updated": today_iso(),
                }
            )
            break
    save_papers(data)
    ensure_local_pdf(paper_id)
    regenerate_kanban()
    return True


def build_codex_prompt(url, paper_id, title):
    note_relpath = paper_note_relpath(paper_id)
    return f"""Use the project skill `paper-reader` to deeply read this paper and update repository state.

Paper URL: {url}
Paper ID: {paper_id}
Title: {title}

Required outcomes:
- Write the DNL note to {note_relpath}
- Update output/papers.json for this paper
- Regenerate output/kanban.html
- Preserve existing paper state unless paper-reader explicitly changes it
- The note body should be primarily in Chinese
- Include a direct PDF link when one is actually available
"""


def read_paper_bg(paper_id, url, title):
    previous_state = snapshot_paper_state(paper_id)
    set_paper_fields(paper_id, progress=5, status="reading")
    regenerate_kanban()
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = paper_log_abspath(paper_id)

    prompt = build_codex_prompt(url, paper_id, title)
    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", suffix=".txt", delete=False
    ) as output_file:
        output_path = output_file.name

    cmd = [
        RESOLVED_CODEX_BIN,
        "exec",
        "--cd",
        ROOT,
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "--output-last-message",
        output_path,
        "--color",
        "never",
        "-m",
        MODEL,
        prompt,
    ]

    try:
        if ensure_local_pdf(paper_id):
            set_paper_fields(paper_id, progress=8, status="reading")
            regenerate_kanban()

        codex_dir = os.path.dirname(RESOLVED_CODEX_BIN)
        env = os.environ.copy()
        env["PATH"] = codex_dir + os.pathsep + env.get("PATH", "")
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n"
                f"Paper ID: {paper_id}\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Command: {' '.join(cmd)}\n\n"
            )
            log_file.flush()

            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            progress_marks = [12, 20, 28, 36, 44, 52, 60, 68, 76, 84, 92]
            mark_idx = 0
            last_tick = time.time()
            last_output_at = time.time()
            logs = []
            note_abspath = os.path.join(ROOT, paper_note_relpath(paper_id))

            while proc.poll() is None:
                now = time.time()
                if proc.stdout:
                    ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if ready:
                        line = proc.stdout.readline()
                        if line:
                            stripped = line.rstrip()
                            log_file.write(stripped + "\n")
                            log_file.flush()
                            logs.append(stripped)
                            if len(logs) > 60:
                                logs = logs[-60:]
                            last_output_at = time.time()

                if mark_idx < len(progress_marks) and now - last_tick >= 4:
                    set_paper_fields(paper_id, progress=progress_marks[mark_idx], status="reading")
                    regenerate_kanban()
                    print(f"[serve.py] {paper_id}: {progress_marks[mark_idx]}%", flush=True)
                    mark_idx += 1
                    last_tick = now

                # Codex occasionally lingers after writing the note; treat long idle time as done.
                if os.path.exists(note_abspath) and now - last_output_at >= 20:
                    log_file.write("[serve.py] Note exists and Codex CLI is idle; terminating process.\n")
                    log_file.flush()
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

            remainder = proc.stdout.read() if proc.stdout else ""
            if remainder:
                for raw_line in remainder.splitlines():
                    stripped = raw_line.rstrip()
                    log_file.write(stripped + "\n")
                    logs.append(stripped)
                log_file.flush()
                logs = logs[-60:]

            if proc.returncode not in (0, -15):
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"codex exited {proc.returncode}")

        if not finalize_read_result(paper_id):
            last_message = ""
            try:
                with open(output_path, encoding="utf-8") as f:
                    last_message = f.read().strip()
            except OSError:
                pass
            raise RuntimeError(
                "codex completed but did not create the expected note file"
                + (f"\n{last_message}" if last_message else "")
            )

        print(f"[serve.py] Complete via Codex CLI: {title[:60]}", flush=True)
    except Exception as exc:
        print(f"[serve.py] Codex CLI error: {exc}", flush=True)
        restore_paper_state(paper_id, previous_state)
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path.endswith(".html") and path not in ("/kanban.html", "/engineering.html"):
            rel_name = path.lstrip("/")
            safe_name = os.path.basename(rel_name)
            html_file = os.path.join(OUTPUT_DIR, safe_name)
            if os.path.exists(html_file):
                body = open(html_file, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return

        if path == "/" or path == "/kanban.html":
            html_file = os.path.join(OUTPUT_DIR, "kanban.html")
            if os.path.exists(html_file):
                body = open(html_file, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        elif path == "/engineering.html":
            ensure_engineering_page()
            if os.path.exists(ENGINEERING_HTML):
                body = open(ENGINEERING_HTML, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        elif path == "/api/papers":
            try:
                data = load_papers()
                for paper in data.get("papers", []):
                    if paper.get("pdf_local_path") and os.path.exists(os.path.join(ROOT, paper["pdf_local_path"])):
                        paper["pdf_url"] = local_pdf_api_path(paper["id"])
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_cors()
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(500)
                self.send_cors()
                self.end_headers()

        elif path.startswith("/api/pdf/"):
            paper_id = urllib.parse.unquote(path[len("/api/pdf/"):])
            paper = find_paper_by_id(paper_id)
            pdf_file = ""
            if paper:
                local_relpath = paper.get("pdf_local_path") or paper_pdf_relpath_for_paper(paper)
                pdf_file = os.path.join(ROOT, local_relpath)
                if not os.path.exists(pdf_file):
                    ensured = ensure_local_pdf(paper_id)
                    pdf_file = ensured or pdf_file
            if pdf_file and os.path.exists(pdf_file):
                body = open(pdf_file, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(body)))
                self.send_cors()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.send_cors()
                self.end_headers()

        elif path == "/api/health":
            body = json.dumps(
                {
                    "ok": True,
                    "model": MODEL,
                    "provider": "codex-cli",
                    "codex_bin": RESOLVED_CODEX_BIN,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/engineering-status":
            context = latest_search_context()
            status = load_engineering_status()
            status["expected_topic"] = context["topic"]
            status["page_ready"] = os.path.exists(ENGINEERING_HTML)
            body = json.dumps(status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        elif path.startswith("/api/notes/"):
            paper_id = path[len("/api/notes/"):]
            paper = find_paper_by_id(paper_id)
            note_relpath = paper.get("note_path") if paper else None
            note_file = os.path.join(ROOT, note_relpath) if note_relpath else ""
            if os.path.exists(note_file):
                body = open(note_file, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_cors()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.send_cors()
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/read-paper":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            url = body.get("url", "").strip()
            paper_id = body.get("paper_id", "").strip()
            title = body.get("title", "").strip()

            if not url or not paper_id:
                self.send_response(400)
                self.end_headers()
                return

            threading.Thread(
                target=read_paper_bg,
                args=(paper_id, url, title),
                daemon=True,
            ).start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "paper_id": paper_id}).encode())

        elif self.path == "/api/generate-engineering":
            started = maybe_start_engineering_generation(force=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "status": "started" if started else "running",
                        "topic": latest_search_context()["topic"],
                    }
                ).encode()
            )

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    if os.path.exists(PAPERS_JSON) and os.path.exists(KANBAN_TEMPLATE):
        regenerate_kanban()
    if os.path.exists(PAPERS_JSON) and os.path.exists(ENGINEERING_TEMPLATE):
        ensure_engineering_page()
    print("MyResearchClaw API server")
    print(f"  Listening on http://localhost:{PORT}")
    print("  Provider: Codex CLI")
    print(f"  Model: {MODEL}")
    print(f"  Codex binary: {RESOLVED_CODEX_BIN}")
    print("  Open http://localhost:5678/kanban.html")
    print("  Ctrl+C to stop\n")
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
