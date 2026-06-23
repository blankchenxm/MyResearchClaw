#!/usr/bin/env python3
"""
MyResearchClaw local API server.

Usage:
  cd /home/meng/Agent/MyResearchClaw
  python serve.py

Then open http://localhost:5678/kanban.html

Optional environment variables:
  MYRESEARCHCLAW_MODEL       default: claude-sonnet-4-6
  MYRESEARCHCLAW_CLAUDE_BIN  default: claude
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
PROJECTS_DIR = os.path.join(OUTPUT_DIR, "projects")
PAPERS_JSON = os.path.join(OUTPUT_DIR, "papers.json")
NOTES_DIR = os.path.join(OUTPUT_DIR, "notes")
PDFS_DIR = os.path.join(OUTPUT_DIR, "pdfs")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
CHATS_DIR = os.path.join(OUTPUT_DIR, "chats")
ENGINEERING_STATUS_JSON = os.path.join(OUTPUT_DIR, "engineering_status.json")
SCOUT_STATUS_JSON = os.path.join(OUTPUT_DIR, "scout_status.json")
TOKEN_USAGE_JSON = os.path.join(OUTPUT_DIR, "token_usage.json")

_ROUND_RE = re.compile(r"\bRound\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
SKILLS_DIR = os.path.join(ROOT, "skills")
KANBAN_TEMPLATE = os.path.join(SKILLS_DIR, "conference-scout", "assets", "kanban.html")
KANBAN_HTML = os.path.join(OUTPUT_DIR, "kanban.html")
ENGINEERING_TEMPLATE = os.path.join(SKILLS_DIR, "engineering-scout", "assets", "engineering.html")
ENGINEERING_HTML = os.path.join(OUTPUT_DIR, "engineering.html")

MODEL = (
    os.environ.get("MYRESEARCHCLAW_MODEL", "claude-sonnet-4-6").strip()
    or "claude-sonnet-4-6"
)
CLAUDE_BIN = (
    os.environ.get("MYRESEARCHCLAW_CLAUDE_BIN", "claude").strip() or "claude"
)


def resolve_claude_bin():
    if os.path.isabs(CLAUDE_BIN) and os.path.exists(CLAUDE_BIN):
        return CLAUDE_BIN
    resolved = shutil.which(CLAUDE_BIN)
    if resolved:
        return resolved
    # Common npm-installed Claude Code locations
    for fallback in (
        os.path.expanduser("~/.npm-global/bin/claude"),
        "/home/wangmingke/.nvm/versions/node/v24.14.1/bin/claude",
        "/usr/local/bin/claude",
    ):
        if os.path.exists(fallback):
            return fallback
    return CLAUDE_BIN


RESOLVED_CLAUDE_BIN = resolve_claude_bin()


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


def strip_html_tags(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def topic_project_dir(topic_or_slug):
    slug = topic_or_slug if re.fullmatch(r"[a-z0-9-]+", topic_or_slug or "") else slugify_topic(topic_or_slug)
    return os.path.join(PROJECTS_DIR, slug)


def topic_papers_relpath(topic_or_slug):
    slug = topic_or_slug if re.fullmatch(r"[a-z0-9-]+", topic_or_slug or "") else slugify_topic(topic_or_slug)
    return f"projects/{slug}/papers.html"


def topic_engineering_relpath(topic_or_slug):
    slug = topic_or_slug if re.fullmatch(r"[a-z0-9-]+", topic_or_slug or "") else slugify_topic(topic_or_slug)
    return f"projects/{slug}/engineering.html"


def topic_papers_abspath(topic_or_slug):
    return os.path.join(OUTPUT_DIR, topic_papers_relpath(topic_or_slug))


def topic_engineering_abspath(topic_or_slug):
    return os.path.join(OUTPUT_DIR, topic_engineering_relpath(topic_or_slug))


def chat_key(topic, page_type):
    return f"{slugify_topic(topic)}-{page_type}"


def chat_path(topic, page_type):
    return os.path.join(CHATS_DIR, f"{chat_key(topic, page_type)}.json")


def load_chat_history(topic, page_type):
    return load_json_file(chat_path(topic, page_type), {"topic": topic, "page_type": page_type, "messages": []})


def save_chat_history(topic, page_type, history):
    os.makedirs(CHATS_DIR, exist_ok=True)
    payload = {"topic": topic, "page_type": page_type, "messages": history}
    save_json_file(chat_path(topic, page_type), payload)


def build_project_context(topic, page_type):
    if page_type == "papers":
        data = load_papers()
        papers = [p for p in data.get("papers", []) if p.get("topic") == topic]
        lines = [
            f"Topic: {topic}",
            f"Project page type: papers",
            f"Paper count: {len(papers)}",
        ]
        done_notes = []
        for idx, paper in enumerate(papers[:12], start=1):
            lines.extend(
                [
                    f"{idx}. {paper.get('title','Untitled')} — {paper.get('venue','Unknown')} {paper.get('year','')}",
                    f"   Authors: {paper.get('authors','Unknown authors')}",
                    f"   Summary EN: {paper.get('summary_en','')}",
                    f"   Summary ZH: {paper.get('summary_zh','')}",
                    f"   Status: {paper.get('status','unread')} | Progress: {paper.get('progress',0)}",
                ]
            )
            # Include deep-reading note content for finished papers
            note_path = paper.get("note_path")
            if note_path and paper.get("status") == "done":
                note_abs = os.path.join(ROOT, note_path)
                if os.path.exists(note_abs):
                    try:
                        with open(note_abs, encoding="utf-8") as nf:
                            note_text = nf.read()[:4000]
                        done_notes.append(
                            f"\n--- 精读笔记: {paper.get('title','Untitled')} ---\n{note_text}\n---"
                        )
                    except OSError:
                        pass
        if done_notes:
            lines.append("\n已完成精读笔记 (deep-reading notes for finished papers):")
            lines.extend(done_notes)
        return "\n".join(lines)

    slug = slugify_topic(topic)
    engineering_candidates = [
        topic_engineering_abspath(slug),
        os.path.join(OUTPUT_DIR, f"{slug}-engineering.html"),
        ENGINEERING_HTML,
    ]
    html_text = ""
    for path in engineering_candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                html_text = f.read()
            if topic in html_text or path == engineering_candidates[0]:
                break
    context_text = strip_html_tags(html_text)[:12000]
    return f"Topic: {topic}\nProject page type: engineering\nPage content:\n{context_text}"


def run_chat_query(topic, page_type, message, history):
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"chat-{chat_key(topic, page_type)}.log")
    context = build_project_context(topic, page_type)
    history_lines = []
    for item in history[-10:]:
        role = item.get("role", "assistant").upper()
        history_lines.append(f"{role}: {item.get('content','')}")
    history_block = "\n".join(history_lines) if history_lines else "(empty)"
    prompt = f"""You are Claude (Sonnet 4.6), the embedded assistant for a MyResearchClaw project page. You are NOT Codex, GPT, or any other model.

Page topic: {topic}
Page type: {page_type}

You already know the current project context below, including deep-reading notes for finished papers. Use it as primary context. You may also use web search when needed.

Project context:
{context}

Conversation so far:
{history_block}

User question:
{message}

Instructions:
- Answer directly and concisely.
- When the user asks about specific papers, reference the 精读笔记 (deep-reading note) content above if available.
- If web search is useful for context beyond what's in the notes, use it.
- Keep answers grounded in the project context.
"""

    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".txt", delete=False) as output_file:
        output_path = output_file.name

    cmd = [
        RESOLVED_CLAUDE_BIN,
        "-p",
        prompt,
        "--model",
        MODEL,
        "--permission-mode",
        "bypassPermissions",
        "--add-dir",
        ROOT,
        "--output-format",
        "json",
    ]

    claude_dir = os.path.dirname(RESOLVED_CLAUDE_BIN)
    env = os.environ.copy()
    env["PATH"] = claude_dir + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=240,
        )
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n"
                f"Topic: {topic}\nPage type: {page_type}\nUser: {message}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Output:\n{proc.stdout}\n"
                f"Stderr:\n{proc.stderr}\n"
            )
        if proc.returncode != 0:
            raise RuntimeError(
                (proc.stderr or proc.stdout).strip() or f"claude exited {proc.returncode}"
            )
        answer = ""
        try:
            payload = json.loads(proc.stdout)
            answer = (payload.get("result") or "").strip()
        except Exception:
            answer = proc.stdout.strip()
        return answer
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


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


def infer_timeline_role(paper):
    explicit = (paper.get("timeline_role") or "").strip().lower()
    if explicit:
        return explicit
    tags = {str(tag).strip().lower() for tag in (paper.get("tags") or [])}
    if {"survey", "review", "tutorial"} & tags:
        return "survey"
    if {"breakthrough", "foundation", "foundational", "seminal", "classic"} & tags:
        return "breakthrough"
    if {"frontier", "latest", "recent", "sota"} & tags:
        return "frontier"
    year = int(paper.get("year") or 0)
    if year >= datetime.now().year - 1:
        return "frontier"
    return "timeline"


def timeline_role_meta(paper):
    role = infer_timeline_role(paper)
    mapping = {
        "survey": ("Survey", "role-survey"),
        "breakthrough": ("Breakthrough", "role-breakthrough"),
        "foundation": ("Foundation", "role-breakthrough"),
        "foundational": ("Foundation", "role-breakthrough"),
        "seminal": ("Seminal", "role-breakthrough"),
        "consolidation": ("Consolidation", "role-consolidation"),
        "frontier": ("Frontier", "role-frontier"),
        "timeline": ("Timeline Node", "role-timeline"),
    }
    return role, *mapping.get(role, ("Timeline Node", "role-timeline"))


def timeline_reason_text(paper):
    return (
        (paper.get("timeline_reason_zh") or "").strip()
        or (paper.get("timeline_reason_en") or "").strip()
        or (paper.get("summary_zh") or "").strip()
        or (paper.get("summary_en") or "").strip()
    )


def render_lang_html(zh_text, en_text, tag="div", class_name=""):
    classes = f" {class_name}" if class_name else ""
    zh = escape((zh_text or "").strip())
    en = escape((en_text or "").strip())
    parts = []
    if zh:
        parts.append(f"<{tag} class=\"lang-zh lang-block{classes}\">{zh}</{tag}>")
    if en:
        parts.append(f"<{tag} class=\"lang-en lang-block{classes}\">{en}</{tag}>")
    if not parts:
        parts.append(f"<{tag} class=\"lang-zh lang-block{classes}\"></{tag}>")
    return "".join(parts)


def render_lang_inline(zh_text, en_text):
    zh = escape((zh_text or "").strip())
    en = escape((en_text or "").strip())
    parts = []
    if zh:
        parts.append(f"<span class=\"lang-zh lang-inline\">{zh}</span>")
    if en:
        parts.append(f"<span class=\"lang-en lang-inline\">{en}</span>")
    if not parts:
        parts.append("<span class=\"lang-zh lang-inline\"></span>")
    return "".join(parts)


def timeline_reason_pair(paper):
    zh = (
        (paper.get("timeline_reason_zh") or "").strip()
        or (paper.get("summary_zh") or "").strip()
        or (paper.get("timeline_reason_en") or "").strip()
        or (paper.get("summary_en") or "").strip()
    )
    en = (
        (paper.get("timeline_reason_en") or "").strip()
        or (paper.get("summary_en") or "").strip()
        or (paper.get("timeline_reason_zh") or "").strip()
        or (paper.get("summary_zh") or "").strip()
    )
    return zh, en


def summarize_timeline(papers):
    counts = {"survey": 0, "breakthrough": 0, "consolidation": 0, "frontier": 0, "other": 0}
    years = []
    for paper in papers:
        role = infer_timeline_role(paper)
        if role in {"foundation", "foundational", "seminal"}:
            role = "breakthrough"
        if role not in counts:
            role = "other"
        counts[role] += 1
        year = int(paper.get("year") or 0)
        if year:
            years.append(year)
    span = f"{min(years)}-{max(years)}" if years else "Unknown"
    return counts, span


def build_timeline_overview(papers, venues):
    counts, span = summarize_timeline(papers)
    total = len(papers)
    zh = (
        f"本次共整理 {total} 篇论文，时间线覆盖 {span}。其中包含 "
        f"{counts['survey']} 篇 survey、{counts['breakthrough']} 篇 breakthrough / foundation、"
        f"{counts['consolidation']} 篇 consolidation，以及 {counts['frontier']} 篇 frontier。"
        f"检索范围重点覆盖：{venues or 'selected top venues'}。"
    )
    en = (
        f"This topic timeline contains {total} papers spanning {span}. It includes "
        f"{counts['survey']} survey papers, {counts['breakthrough']} breakthrough/foundation papers, "
        f"{counts['consolidation']} consolidation papers, and {counts['frontier']} frontier papers. "
        f"Venue sweep focused on: {venues or 'selected top venues'}."
    )
    return counts, span, zh, en


def render_timeline_items(papers):
    ordered = sorted(
        papers,
        key=lambda paper: (int(paper.get("year") or 0), int(paper.get("rank") or 9999), paper.get("title") or ""),
    )
    rendered = []
    for idx, paper in enumerate(ordered, start=1):
        _, label, css = timeline_role_meta(paper)
        reason_zh, reason_en = timeline_reason_pair(paper)
        year = escape(str(paper.get("year") or "Unknown"))
        card_html = render_paper_card(idx, paper)
        rendered.append(
            f"""
            <article class="timeline-entry">
              <div class="timeline-spine">
                <div class="timeline-dot"></div>
              </div>
              <div class="timeline-marker">
                <div class="timeline-year">{year}</div>
                <div class="timeline-top">
                  <span class="timeline-role {css}">{escape(label)}</span>
                </div>
                <div class="timeline-note">{render_lang_html(reason_zh[:220], reason_en[:220], tag="div")}</div>
              </div>
              <div class="timeline-card-wrap">
                {card_html}
              </div>
            </article>"""
        )
    return "\n".join(rendered)


def _check_pdf_fetch_failed(paper_id):
    """Return True if the paper's fetch pipeline step failed with no accessible PDF."""
    tmp_dir = os.path.join(OUTPUT_DIR, "tmp", paper_id)
    if not os.path.isdir(tmp_dir):
        return False
    for fname in os.listdir(tmp_dir):
        if fname.endswith("_fetch.json"):
            fetch_data = load_json_file(os.path.join(tmp_dir, fname), {})
            if fetch_data.get("status") == "error":
                return True
    return False


def render_progress_state(paper):
    progress = int(paper.get("progress") or 0)
    status = (paper.get("status") or "").strip()
    pipeline_status = (paper.get("pipeline_status") or "").strip()
    note_path = paper.get("note_path")

    # Authoritative completion signal: pipeline_status == "complete" plus an existing
    # note file on disk. Catches the case where serve.py was restarted mid-run but
    # write_note.py finished and updated papers.json. Without this, the kanban would
    # stay on "精读中..." forever because the heartbeat-driven status/progress fields
    # were never advanced to terminal values.
    if (
        pipeline_status == "complete"
        and note_path
        and os.path.exists(os.path.join(ROOT, note_path))
    ):
        status = "done"
        progress = 100

    fill_class = "progress-fill"
    label_class = "progress-label"
    label_html = ""

    if pipeline_status == "pdf_fetch_failed":
        label_class += " failed"
        label_html = render_lang_inline("PDF 获取失败", "PDF fetch failed")
    elif status == "done" or progress >= 100:
        fill_class += " done"
        label_class += " done"
        label_html = render_lang_inline("✓ 已完成", "✓ Complete")
    elif progress > 0 or status == "reading":
        fill_class += " active"
        label_html = render_lang_inline(f"精读中... {progress}%", f"Reading... {progress}%")

    if pipeline_status == "pdf_fetch_failed":
        button_html = (
            '<button data-role="read-btn" class="btn btn-read" disabled>'
            f'{render_lang_inline("📎 等待 PDF 上传", "📎 Awaiting PDF")}'
            "</button>"
        )
    elif status == "done":
        button_html = (
            f'<button data-role="read-btn" class="btn btn-done" onclick="navigateTo(\'notes\', \'{escape_js(paper["id"])}\')">'
            f'{render_lang_inline("✅ 已完成", "✅ Done")}'
            "</button>"
        )
    elif note_path and os.path.exists(os.path.join(ROOT, note_path)):
        button_html = (
            f'<button data-role="read-btn" class="btn btn-notes" onclick="navigateTo(\'notes\', \'{escape_js(paper["id"])}\')">'
            f'{render_lang_inline("📄 查看笔记", "📄 View Notes")}'
            "</button>"
        )
    elif progress > 0 or status == "reading":
        button_html = (
            '<button data-role="read-btn" class="btn btn-read reading" disabled>'
            f'{render_lang_inline("⏳ 精读中...", "⏳ Reading...")}'
            "</button>"
        )
    else:
        button_html = (
            '<button data-role="read-btn" class="btn btn-read" '
            f'onclick="triggerRead(\'{escape_js(paper["id"])}\','
            f'\'{escape_js(paper.get("url") or "")}\','
            f'\'{escape_js(paper.get("title") or "")}\')">{render_lang_inline("📖 精读论文", "📖 Read Paper")}</button>'
        )

    return progress, fill_class, label_class, label_html, button_html


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
    progress, fill_class, label_class, label_html, button_html = render_progress_state(paper)
    tags_html = render_tags(paper.get("tags"))
    summary_en = (paper.get("summary_en") or "").strip()
    summary_zh = (paper.get("summary_zh") or "").strip()
    paper_url = escape(paper.get("url") or "")
    pdf_url = escape(infer_pdf_url(paper))
    title = escape(paper.get("title") or "Untitled")
    authors = escape(paper.get("authors") or "Unknown authors")
    _, role_label, role_css = timeline_role_meta(paper)
    role_reason_zh, role_reason_en = timeline_reason_pair(paper)

    tags_block = f"\n          {tags_html}" if tags_html else ""

    # Show abstract (summary_zh/en) separately from role_reason
    summary_zh_text = (paper.get("summary_zh") or "").strip()
    summary_en_text = (paper.get("summary_en") or "").strip()
    summary_block_html = ""
    if summary_zh_text or summary_en_text:
        summary_block_html = f"""
        <div class="summary-block">
          {render_lang_html(summary_zh_text, summary_en_text, tag="div", class_name="summary-copy")}
        </div>"""

    return f"""
      <!-- ── Paper {idx} ── -->
      <div class="{status_card_class(paper)}" data-id="{escape(paper["id"])}" data-url="{paper_url}" data-pdf-url="{pdf_url}" data-progress="{progress}">
        <div class="card-header">
          <div class="card-title"><a href="{paper_url}" target="_blank">{title}</a></div>
          <span class="citations {citations_class}">{citations_text}</span>
        </div>
        <div class="card-role-row">
          <span class="timeline-role {role_css}">{escape(role_label)}</span>
          <span class="{venue_class}">{escape(venue_text)}</span>
        </div>
        <div class="card-authors">{authors}</div>
        <div class="card-role-reason-main">
          {render_lang_html(role_reason_zh, role_reason_en, tag="div", class_name="role-reason-copy")}
        </div>
        {summary_block_html}
        <div class="progress-row">
          <div class="progress-track"><div class="{fill_class}" style="width:{progress}%"></div></div>
          <span class="{label_class}">{label_html}</span>
        </div>
        <div class="pdf-upload-zone" data-paper-id="{escape(paper['id'])}" style="{'display:none' if (paper.get('pipeline_status') or '') != 'pdf_fetch_failed' else ''}">
          <div class="pdf-upload-hint">
            <span class="lang-zh lang-inline">📎 PDF 获取失败，请手动上传 PDF</span>
            <span class="lang-en lang-inline">📎 PDF fetch failed — upload manually</span>
          </div>
          <div class="pdf-drop-area">
            <span class="lang-zh lang-block">拖拽 PDF 到此处，或点击选择文件</span>
            <span class="lang-en lang-block">Drop PDF here, or click to select</span>
            <input type="file" accept=".pdf,application/pdf" style="display:none" />
          </div>
        </div>
        <div class="card-actions">
          <a href="{paper_url}" target="_blank" class="btn btn-view">{render_lang_inline("🔗 查看论文", "🔗 View Paper")}</a>
          {button_html}
        </div>
      </div>"""


def render_dashboard_html(active_topic, active_year_range, active_venues, engineering_link, papers):
    template = load_kanban_template()
    timeline_items = render_timeline_items(papers)
    counts, span, overview_zh, overview_en = build_timeline_overview(papers, active_venues)
    return (
        template.replace("{{LAST_UPDATED}}", escape(today_iso()))
        .replace("{{ACTIVE_TOPIC}}", escape(active_topic))
        .replace("{{ACTIVE_YEAR_RANGE}}", escape(active_year_range))
        .replace("{{ACTIVE_VENUES}}", escape(active_venues))
        .replace("{{ENGINEERING_LINK}}", engineering_link)
        .replace("{{TOTAL_PAPERS}}", str(len(papers)))
        .replace("{{TIMELINE_SPAN}}", escape(span))
        .replace("{{SURVEY_COUNT}}", str(counts["survey"]))
        .replace("{{BREAKTHROUGH_COUNT}}", str(counts["breakthrough"]))
        .replace("{{CONSOLIDATION_COUNT}}", str(counts["consolidation"]))
        .replace("{{FRONTIER_COUNT}}", str(counts["frontier"]))
        .replace("{{OVERVIEW_ZH}}", escape(overview_zh))
        .replace("{{OVERVIEW_EN}}", escape(overview_en))
        .replace("{{TIMELINE_ITEMS}}", timeline_items)
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
            <div class="topic-title-wrap">
              <div class="topic-eyebrow">Research Theme</div>
              <h2>{escape(row["topic"])}</h2>
            </div>
            <div class="topic-top-right">
              <div class="topic-count">{row["paper_count"]} papers</div>
              <button class="topic-delete" title="Delete this theme" onclick="deleteTopic('{escape(row["topic"])}', '{escape(row["slug"])}', {row["paper_count"]})">🗑️</button>
            </div>
          </div>
          <div class="topic-meta">
            <span><span class="meta-label">检索范围</span>{escape(row["year_range"])}</span>
            <span><span class="meta-label">创建于</span>{escape(row["date"])}</span>
          </div>
          <p class="topic-venues">{escape(row["venues"])}</p>
          <div class="topic-actions">
            <a href="/projects/{row["slug"]}/papers.html" class="action-papers">
              <span class="action-icon">📚</span>
              <span class="action-text">
                <span class="action-title">Open Papers</span>
                <span class="action-desc">论文时间线 · 精读笔记</span>
              </span>
            </a>
            <a href="/projects/{row["slug"]}/engineering.html" class="action-engineering">
              <span class="action-icon">🛠️</span>
              <span class="action-text">
                <span class="action-title">Engineering View</span>
                <span class="action-desc">开源仓库 · 工程实现</span>
              </span>
            </a>
          </div>
        </article>"""
        for row in topic_rows
    )

    # Pre-compute year selector options
    _cur_year = datetime.now().year
    _year_opts_start = "\n".join(
        f'<option value="{y}"{" selected" if y == _cur_year - 5 else ""}>{y}</option>'
        for y in range(2010, _cur_year + 1)
    )
    _year_opts_end = "\n".join(
        f'<option value="{y}"{" selected" if y == _cur_year else ""}>{y}</option>'
        for y in range(2010, _cur_year + 1)
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
.wrap {{ max-width:96vw; margin:0 auto; padding:28px 28px 80px; }}
.theme-toggle {{
  position:fixed; top:16px; right:16px; z-index:9999; width:40px; height:40px; border-radius:50%;
  border:1px solid var(--line); background:var(--panel); color:var(--text); cursor:pointer; font-size:16px;
}}
.lang-block {{ display:block; }}
.lang-inline {{ display:inline; }}
.lang-en {{ display:none !important; }}
.lang-zh.lang-block {{ display:block; }}
.lang-zh.lang-inline {{ display:inline; }}
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
.topic-title-wrap {{ flex:1; min-width:0; }}
.topic-top-right {{ display:flex; gap:10px; align-items:center; flex-shrink:0; }}
.topic-eyebrow {{ font:600 13px 'JetBrains Mono', monospace; color:var(--cyan); text-transform:uppercase; letter-spacing:.12em; margin-bottom:10px; }}
.topic-card h2 {{ font-size:36px; line-height:1.22; font-weight:900; }}
.topic-count {{ white-space:nowrap; border:1px solid var(--line); border-radius:999px; padding:7px 14px; font:600 14px 'JetBrains Mono', monospace; color:var(--blue); }}
.topic-delete {{
  width:40px; height:40px; border-radius:10px; border:1px solid var(--line);
  background:rgba(255,255,255,0.04); color:var(--muted); cursor:pointer;
  font-size:18px; display:inline-flex; align-items:center; justify-content:center;
  transition:all .15s;
}}
.topic-delete:hover {{ color:#ff8d6b; border-color:rgba(255,141,107,0.4); background:rgba(255,141,107,0.08); }}
.topic-meta {{ display:flex; gap:18px; flex-wrap:wrap; margin-bottom:14px; color:var(--dim); font-size:16px; }}
.topic-meta .meta-label {{ font:600 12px 'JetBrains Mono', monospace; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; margin-right:6px; }}
.topic-venues {{ color:var(--dim); line-height:1.8; margin-bottom:18px; font-size:16px; }}
.topic-actions {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }}
.topic-actions a {{
  display:flex; align-items:center; gap:16px; text-decoration:none; border:1px solid var(--line);
  border-radius:16px; padding:18px 20px; color:var(--text); background:rgba(255,255,255,0.04);
  transition:all .15s;
}}
.topic-actions a:hover {{ transform:translateY(-1px); }}
.action-icon {{ font-size:30px; line-height:1; }}
.action-text {{ display:flex; flex-direction:column; gap:5px; min-width:0; }}
.action-title {{ font-weight:700; font-size:18px; }}
.action-desc {{ font-size:15px; color:var(--dim); }}
.topic-actions .action-papers {{ border-color:rgba(105,166,255,0.18); background:rgba(105,166,255,0.06); }}
.topic-actions .action-papers:hover {{ border-color:rgba(105,166,255,0.35); }}
.topic-actions .action-papers .action-title {{ color:var(--blue); }}
.topic-actions .action-engineering {{ border-color:rgba(56,217,199,0.18); background:rgba(56,217,199,0.06); }}
.topic-actions .action-engineering:hover {{ border-color:rgba(56,217,199,0.35); }}
.topic-actions .action-engineering .action-title {{ color:var(--cyan); }}
@media (max-width: 720px) {{
  .wrap {{ padding:16px 16px 60px; }}
  .hero {{ padding:22px 20px; }}
  .hero h1 {{ font-size:30px; }}
  .topic-top {{ flex-direction:column; }}
}}

/* ── Scout: add-button card ── */
.scout-add-btn {{
  display:flex; align-items:center; gap:14px; cursor:pointer;
  background:var(--panel); border:1.5px dashed rgba(105,166,255,0.3);
  border-radius:22px; padding:22px 26px; color:var(--blue);
  transition:all .15s; user-select:none;
}}
.scout-add-btn:hover {{ border-color:rgba(105,166,255,0.6); background:rgba(105,166,255,0.07); }}
.scout-add-icon {{ font-size:26px; line-height:1; font-weight:300; }}
.scout-add-label {{ font-weight:700; font-size:17px; }}
.scout-add-sub {{ font-size:13px; color:var(--dim); margin-top:2px; }}

/* ── Scout: form panel ── */
.scout-form-panel {{
  background:var(--panel); border:1px solid rgba(105,166,255,0.18);
  border-radius:22px; padding:28px 28px 22px;
}}
.scout-form-title {{ font-weight:800; font-size:20px; margin-bottom:20px; color:var(--text); }}
.scout-form-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px 20px; }}
.scout-form-full {{ grid-column:1 / -1; }}
.scout-field {{ display:flex; flex-direction:column; gap:6px; }}
.scout-field label {{ font:600 11px 'JetBrains Mono', monospace; color:var(--muted); text-transform:uppercase; letter-spacing:.09em; }}
.scout-field input, .scout-field select, .scout-field textarea {{
  background:var(--panel-soft); border:1px solid var(--line); border-radius:10px;
  color:var(--text); font-size:14px; padding:9px 13px; outline:none;
  font-family:inherit; resize:none; transition:border-color .15s;
}}
.scout-field input:focus, .scout-field select:focus, .scout-field textarea:focus {{
  border-color:rgba(105,166,255,0.5);
}}
.scout-field textarea {{ min-height:72px; line-height:1.6; }}
.scout-year-row {{ display:flex; gap:8px; align-items:center; }}
.scout-year-row select {{ flex:1; }}
.scout-year-sep {{ color:var(--muted); font-size:13px; }}

/* Venue chips */
.venue-chip-input-row {{ display:flex; gap:8px; }}
.venue-chip-input-row input {{ flex:1; }}
.venue-chip-add-btn {{
  background:rgba(105,166,255,0.12); border:1px solid rgba(105,166,255,0.25);
  border-radius:8px; color:var(--blue); cursor:pointer; font-size:14px;
  padding:0 14px; white-space:nowrap; transition:all .15s;
}}
.venue-chip-add-btn:hover {{ background:rgba(105,166,255,0.22); }}
.venue-chips {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; min-height:10px; }}
.v-chip {{
  display:inline-flex; align-items:center; gap:5px; background:rgba(56,217,199,0.12);
  border:1px solid rgba(56,217,199,0.25); border-radius:999px;
  padding:3px 10px 3px 12px; font-size:13px; color:var(--cyan);
}}
.v-chip-del {{ cursor:pointer; opacity:.6; font-size:12px; line-height:1; }}
.v-chip-del:hover {{ opacity:1; }}

.scout-form-actions {{ display:flex; gap:10px; margin-top:18px; }}
.scout-submit-btn {{
  background:rgba(105,166,255,0.15); border:1px solid rgba(105,166,255,0.35);
  border-radius:10px; color:var(--blue); cursor:pointer; font:600 14px inherit;
  padding:10px 24px; transition:all .15s;
}}
.scout-submit-btn:hover {{ background:rgba(105,166,255,0.28); }}
.scout-cancel-btn {{
  background:transparent; border:1px solid var(--line); border-radius:10px;
  color:var(--muted); cursor:pointer; font:500 14px inherit; padding:10px 18px;
  transition:all .15s;
}}
.scout-cancel-btn:hover {{ color:var(--text); border-color:rgba(255,255,255,0.2); }}

/* ── Scout: progress panel ── */
.scout-progress-panel {{
  background:var(--panel); border:1px solid var(--line);
  border-radius:22px; padding:24px 28px;
}}
.scout-progress-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }}
.scout-progress-title {{ font-weight:700; font-size:17px; }}
.scout-phase-badge {{
  font:600 11px 'JetBrains Mono', monospace; text-transform:uppercase;
  letter-spacing:.09em; padding:4px 10px; border-radius:999px;
  background:rgba(105,166,255,0.12); color:var(--blue); border:1px solid rgba(105,166,255,0.2);
}}
.scout-track {{
  height:6px; border-radius:3px; background:rgba(255,255,255,0.07);
  overflow:hidden; margin-bottom:10px;
}}
.scout-fill {{
  height:100%; border-radius:3px;
  background:linear-gradient(90deg, var(--blue), var(--cyan));
  transition:width 1s ease;
}}
.scout-progress-msg {{ font-size:13px; color:var(--dim); }}
.scout-error-msg {{ color:#ff8d6b; font-size:13px; margin-top:8px; }}

/* ── Scout: candidates confirmation panel ── */
.scout-confirm-panel {{
  background:var(--panel); border:1px solid rgba(255,214,110,0.2);
  border-radius:22px; padding:24px 28px;
}}
.scout-confirm-title {{ font-weight:700; font-size:18px; margin-bottom:6px; }}
.scout-confirm-sub {{ font-size:13px; color:var(--dim); margin-bottom:18px; }}
.scout-tbl-wrap {{ overflow-x:auto; margin-bottom:16px; }}
.scout-tbl {{
  width:100%; border-collapse:collapse; font-size:13px;
}}
.scout-tbl th {{
  text-align:left; font:600 11px 'JetBrains Mono',monospace;
  text-transform:uppercase; letter-spacing:.08em;
  color:var(--blue); padding:7px 10px; border-bottom:1px solid var(--line);
  white-space:nowrap;
}}
.scout-tbl td {{ padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.04); vertical-align:top; }}
.scout-tbl tr:hover td {{ background:rgba(255,255,255,0.03); }}
.scout-tbl .td-check {{ width:32px; }}
.scout-tbl .td-title {{ max-width:320px; }}
.scout-tbl .td-title a {{ color:var(--text); text-decoration:none; }}
.scout-tbl .td-title a:hover {{ color:var(--blue); }}
.scout-tbl .td-num {{ color:var(--dim); text-align:right; }}
.scout-tbl .pdf-ok {{ color:var(--cyan); }}
.scout-tbl .pdf-no {{ color:var(--muted); }}
.scout-sel-all {{ font-size:12px; color:var(--muted); cursor:pointer; margin-bottom:10px; }}
.scout-sel-all:hover {{ color:var(--text); }}

.scout-adjust-row {{ margin-bottom:16px; }}
.scout-adjust-row label {{ font:600 11px 'JetBrains Mono',monospace; color:var(--muted); text-transform:uppercase; letter-spacing:.09em; display:block; margin-bottom:6px; }}
.scout-adjust-row input {{
  width:100%; background:var(--panel-soft); border:1px solid var(--line);
  border-radius:8px; color:var(--text); font-size:13px; padding:8px 12px; outline:none; font-family:inherit;
}}
.scout-confirm-actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
.scout-confirm-btn {{
  background:rgba(56,217,199,0.14); border:1px solid rgba(56,217,199,0.3);
  border-radius:10px; color:var(--cyan); cursor:pointer; font:600 14px inherit;
  padding:10px 22px; transition:all .15s;
}}
.scout-confirm-btn:hover {{ background:rgba(56,217,199,0.25); }}
.scout-readjust-btn {{
  background:transparent; border:1px solid var(--line); border-radius:10px;
  color:var(--muted); cursor:pointer; font:500 14px inherit; padding:10px 18px;
  transition:all .15s;
}}
.scout-readjust-btn:hover {{ color:var(--text); }}
</style>
</head>
<body>
  <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>
  <div class="wrap">
    <section class="hero">
      <div class="hero-eyebrow">MyResearchClaw</div>
      <h1>
        <span class="lang-zh lang-inline">Topic Navigator</span>
        <span class="lang-en lang-inline">Topic Navigator</span>
      </h1>
      <p>
        <span class="lang-zh lang-block">每个方框对应一个研究主题（Research Theme）。点击 <strong>Open Papers</strong> 进入论文时间线 + 精读笔记，点击 <strong>Engineering View</strong> 查看开源实现 + 工程信号，点击右上角 <strong>🗑️</strong> 可清除该主题的全部内容（论文、笔记、PDF、项目对话）。</span>
        <span class="lang-en lang-block">Each card is one Research Theme. <strong>Open Papers</strong> → paper timeline + deep-reading notes. <strong>Engineering View</strong> → open-source repos + engineering signals. <strong>🗑️</strong> in the top-right deletes everything for that theme (papers, notes, PDFs, project chat).</span>
      </p>
    </section>
    <section class="topics">

      <!-- ── Add New Theme Button ── -->
      <div class="scout-add-btn" id="scoutAddBtn" onclick="toggleScoutForm()">
        <span class="scout-add-icon">＋</span>
        <div>
          <div class="scout-add-label">新增研究主题 / New Research Theme</div>
          <div class="scout-add-sub">输入 Topic 描述，自动触发 Conference Scout 调研</div>
        </div>
      </div>

      <!-- ── New Theme Form Panel ── -->
      <div class="scout-form-panel" id="scoutFormPanel" style="display:none">
        <div class="scout-form-title">新建调研主题</div>
        <div class="scout-form-grid">
          <div class="scout-field scout-form-full">
            <label>Topic 名称（简短关键词）</label>
            <input type="text" id="sfTopic" placeholder="e.g. Silent Speech Recognition" />
          </div>
          <div class="scout-field scout-form-full">
            <label>详细描述（自然语言，可多句）</label>
            <textarea id="sfDescription" placeholder="描述研究方向、应用场景、你希望找到的论文类型…"></textarea>
          </div>
          <div class="scout-field">
            <label>年份范围</label>
            <div class="scout-year-row">
              <select id="sfYearStart">{_year_opts_start}</select>
              <span class="scout-year-sep">–</span>
              <select id="sfYearEnd">{_year_opts_end}</select>
            </div>
          </div>
          <div class="scout-field">
            <label>领域 / 会议组</label>
            <select id="sfVenueGroup">
              <option value="wearable_sensing">穿戴传感 (wearable_sensing)</option>
              <option value="ai_ml">AI / 机器学习 (ai_ml)</option>
              <option value="iot_systems">IoT 系统 (iot_systems)</option>
              <option value="eda_hardware">EDA / 硬件 (eda_hardware)</option>
              <option value="security">安全 (security)</option>
              <option value="systems">系统 (systems)</option>
              <option value="hci">人机交互 (hci)</option>
            </select>
          </div>
          <div class="scout-field scout-form-full">
            <label>指定会议（可选，输入后按 Enter 添加）</label>
            <div class="venue-chip-input-row">
              <input type="text" id="sfVenueInput" placeholder="e.g. SenSys, IMWUT …" onkeydown="venueInputKey(event)" />
              <button class="venue-chip-add-btn" onclick="addVenueChip()">添加</button>
            </div>
            <div class="venue-chips" id="sfVenueChips"></div>
          </div>
        </div>
        <div class="scout-form-actions">
          <button class="scout-submit-btn" onclick="submitScout()">🔍 开始调研</button>
          <button class="scout-cancel-btn" onclick="toggleScoutForm()">取消</button>
        </div>
      </div>

      <!-- ── Progress Panel ── -->
      <div class="scout-progress-panel" id="scoutProgressPanel" style="display:none">
        <div class="scout-progress-header">
          <div class="scout-progress-title" id="scoutProgressTitle">Conference Scout 运行中…</div>
          <span class="scout-phase-badge" id="scoutPhaseBadge">Phase 1</span>
        </div>
        <div class="scout-track"><div class="scout-fill" id="scoutFill" style="width:0%"></div></div>
        <div class="scout-progress-msg" id="scoutProgressMsg">初始化…</div>
        <div class="scout-error-msg" id="scoutErrorMsg" style="display:none"></div>
      </div>

      <!-- ── Round 4.5 Confirmation Panel ── -->
      <div class="scout-confirm-panel" id="scoutConfirmPanel" style="display:none">
        <div class="scout-confirm-title">Round 4.5 — 候选论文确认</div>
        <div class="scout-confirm-sub" id="scoutConfirmSub">请勾选要保留的论文，然后继续 Round 5-7。</div>
        <div class="scout-sel-all" onclick="toggleSelectAll()">全选 / 全不选</div>
        <div class="scout-tbl-wrap">
          <table class="scout-tbl" id="scoutCandidatesTbl">
            <thead>
              <tr>
                <th class="td-check"></th>
                <th>#</th>
                <th>标题</th>
                <th>Venue</th>
                <th>年份</th>
                <th>引用</th>
                <th>Influential</th>
                <th>PDF</th>
              </tr>
            </thead>
            <tbody id="scoutCandidatesTbody"></tbody>
          </table>
        </div>
        <div class="scout-adjust-row">
          <label>追加 Negative Patterns（逗号分隔，可留空）</label>
          <input type="text" id="sfNegPatterns" placeholder="e.g. wrist-based, review, survey" />
        </div>
        <div class="scout-adjust-row">
          <label>调整 Constraint Terms（逗号分隔，可留空）</label>
          <input type="text" id="sfConstraintTerms" placeholder="e.g. real-time, on-device" />
        </div>
        <div class="scout-confirm-actions">
          <button class="scout-confirm-btn" onclick="confirmScout()">✅ 确认，继续 Round 5-7</button>
          <button class="scout-readjust-btn" onclick="readjustRound4()">↩ 重新调整条件，重跑 Round 4</button>
        </div>
      </div>

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
async function deleteTopic(topic, slug, paperCount) {{
  const confirmMsg = `确认删除主题「${{topic}}」吗？\\n\\n将清除：\\n  · ${{paperCount}} 篇论文记录（papers.json）\\n  · 全部精读笔记和图表 (output/notes/${{slug}}/)\\n  · 下载的 PDF (output/pdfs/${{slug}}/)\\n  · 项目对话历史和日志\\n  · 主题专属页面 (output/projects/${{slug}}/)\\n\\n此操作不可撤销。`;
  if (!confirm(confirmMsg)) return;
  try {{
    const r = await fetch('/api/delete-topic', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ topic, slug }})
    }});
    const data = await r.json();
    if (data.ok) {{
      window.location.reload();
    }} else {{
      alert('删除失败：' + (data.error || '未知错误'));
    }}
  }} catch (e) {{
    alert('删除失败：' + e.message);
  }}
}}

// ── Scout UI ─────────────────────────────────────────────────────────────
let _scoutFormOpen = false;
let _scoutPollTimer = null;
let _scoutCandidates = [];

function toggleScoutForm() {{
  _scoutFormOpen = !_scoutFormOpen;
  document.getElementById('scoutFormPanel').style.display = _scoutFormOpen ? '' : 'none';
  if (_scoutFormOpen) document.getElementById('sfTopic').focus();
}}

function venueInputKey(e) {{
  if (e.key === 'Enter') {{ e.preventDefault(); addVenueChip(); }}
}}

function addVenueChip() {{
  const inp = document.getElementById('sfVenueInput');
  const val = inp.value.trim();
  if (!val) return;
  inp.value = '';
  const chips = document.getElementById('sfVenueChips');
  const chip = document.createElement('span');
  chip.className = 'v-chip';
  chip.dataset.value = val;
  chip.innerHTML = `${{val}} <span class="v-chip-del" onclick="this.parentElement.remove()">×</span>`;
  chips.appendChild(chip);
}}

function _getVenues() {{
  return Array.from(document.querySelectorAll('#sfVenueChips .v-chip'))
              .map(c => c.dataset.value).filter(Boolean);
}}

async function submitScout() {{
  const topic = document.getElementById('sfTopic').value.trim();
  const description = document.getElementById('sfDescription').value.trim();
  const yearStart = parseInt(document.getElementById('sfYearStart').value);
  const yearEnd   = parseInt(document.getElementById('sfYearEnd').value);
  const venueGroup = document.getElementById('sfVenueGroup').value;
  const specificVenues = _getVenues();

  if (!topic) {{ alert('请填写 Topic 名称'); return; }}
  if (yearStart > yearEnd) {{ alert('年份起始不能大于结束'); return; }}

  try {{
    const r = await fetch('/api/start-scout', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ topic, description, year_start: yearStart, year_end: yearEnd, venue_group: venueGroup, specific_venues: specificVenues }})
    }});
    const data = await r.json();
    if (!data.ok) {{ alert('启动失败：' + (data.error || '')); return; }}
    document.getElementById('scoutFormPanel').style.display = 'none';
    _scoutFormOpen = false;
    _showProgressPanel('Phase 1', '初始化…', 0);
    _startPoll();
  }} catch (e) {{
    alert('启动失败：' + e.message);
  }}
}}

function _showProgressPanel(phase, msg, pct) {{
  document.getElementById('scoutProgressPanel').style.display = '';
  document.getElementById('scoutConfirmPanel').style.display = 'none';
  document.getElementById('scoutPhaseBadge').textContent = phase;
  document.getElementById('scoutProgressMsg').textContent = msg;
  document.getElementById('scoutFill').style.width = pct + '%';
  document.getElementById('scoutErrorMsg').style.display = 'none';
}}

function _showConfirmPanel(data) {{
  document.getElementById('scoutProgressPanel').style.display = 'none';
  document.getElementById('scoutConfirmPanel').style.display = '';
  _scoutCandidates = data.candidates || [];
  const n = _scoutCandidates.length;
  document.getElementById('scoutConfirmSub').textContent =
    `共 ${{n}} 篇通过 Round 4，勾选要保留的论文，然后继续 Round 5-7。或追加条件后重跑 Round 4。`;
  if (data.negative_patterns && data.negative_patterns.length)
    document.getElementById('sfNegPatterns').value = data.negative_patterns.join(', ');
  if (data.constraint_terms && data.constraint_terms.length)
    document.getElementById('sfConstraintTerms').value = data.constraint_terms.join(', ');
  _renderCandidatesTable();
}}

function _renderCandidatesTable() {{
  const tbody = document.getElementById('scoutCandidatesTbody');
  tbody.innerHTML = '';
  _scoutCandidates.forEach((p, i) => {{
    const pdfCell = p.pdf_available === 'none' || !p.pdf_available
      ? '<span class="pdf-no">✗</span>'
      : `<span class="pdf-ok">✓ ${{p.pdf_available}}</span>`;
    const titleLink = p.url
      ? `<a href="${{p.url}}" target="_blank">${{_esc(p.title)}}</a>`
      : _esc(p.title);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="td-check"><input type="checkbox" checked data-idx="${{i}}" /></td>
      <td>${{i+1}}</td>
      <td class="td-title">${{titleLink}}<div style="font-size:11px;color:var(--muted);margin-top:2px">${{_esc(p.authors||'')}}</div></td>
      <td>${{_esc(p.venue||'')}}</td>
      <td>${{p.year||''}}</td>
      <td class="td-num">${{p.citations||0}}</td>
      <td class="td-num">${{p.influential_citations||0}}</td>
      <td>${{pdfCell}}</td>`;
    tbody.appendChild(tr);
  }});
}}

function _esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function toggleSelectAll() {{
  const boxes = document.querySelectorAll('#scoutCandidatesTbody input[type=checkbox]');
  const anyUnchecked = Array.from(boxes).some(b => !b.checked);
  boxes.forEach(b => b.checked = anyUnchecked);
}}

async function confirmScout() {{
  const boxes = document.querySelectorAll('#scoutCandidatesTbody input[type=checkbox]');
  const confirmed = _scoutCandidates.filter((_, i) => boxes[i] && boxes[i].checked);
  if (!confirmed.length) {{ alert('请至少选择一篇论文'); return; }}

  const negRaw = document.getElementById('sfNegPatterns').value.trim();
  const constRaw = document.getElementById('sfConstraintTerms').value.trim();
  const negPatterns = negRaw ? negRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  const constraintTerms = constRaw ? constRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

  try {{
    const r = await fetch('/api/confirm-scout', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ confirmed_papers: confirmed, negative_patterns: negPatterns, constraint_terms: constraintTerms }})
    }});
    const data = await r.json();
    if (!data.ok) {{ alert('确认失败：' + (data.error || '')); return; }}
    _showProgressPanel('Phase 2', 'Round 5: 引用扩展中…', 60);
    _startPoll();
  }} catch (e) {{
    alert('确认失败：' + e.message);
  }}
}}

async function readjustRound4() {{
  const negRaw = document.getElementById('sfNegPatterns').value.trim();
  const constRaw = document.getElementById('sfConstraintTerms').value.trim();
  const negPatterns = negRaw ? negRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  const constraintTerms = constRaw ? constRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

  try {{
    const r = await fetch('/api/readjust-scout', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ negative_patterns: negPatterns, constraint_terms: constraintTerms }})
    }});
    const data = await r.json();
    if (!data.ok) {{ alert('重调失败：' + (data.error || '')); return; }}
    _showProgressPanel('Phase 1 (重跑 Round 4)', 'Round 4: 重新过滤候选论文…', 45);
    _startPoll();
  }} catch (e) {{
    alert('重调失败：' + e.message);
  }}
}}

function _roundToPct(round, phase) {{
  if (phase === 1) {{
    const map = {{0:5,1:15,2:30,3:50,4:70,4.5:90}};
    return map[round] || Math.min(5 + round * 15, 90);
  }} else {{
    const map = {{5:65,6:80,6.5:90,7:98}};
    return map[round] || Math.min(60 + round * 8, 98);
  }}
}}

function _startPoll() {{
  if (_scoutPollTimer) clearInterval(_scoutPollTimer);
  _scoutPollTimer = setInterval(_pollScoutStatus, 3000);
  _pollScoutStatus();
}}

async function _pollScoutStatus() {{
  try {{
    const r = await fetch('/api/scout-status');
    if (!r.ok) return;
    const data = await r.json();
    const st = data.status;

    if (st === 'idle') {{
      if (_scoutPollTimer) {{ clearInterval(_scoutPollTimer); _scoutPollTimer = null; }}
      return;
    }}
    if (st === 'running_phase1' || st === 'running_phase2') {{
      const phase = st === 'running_phase1' ? 1 : 2;
      const pct = _roundToPct(data.current_round || 0, phase);
      _showProgressPanel(`Phase ${{phase}}`, data.message || '处理中…', pct);
      document.getElementById('scoutProgressTitle').textContent =
        `Conference Scout — ${{data.topic || ''}}`;
    }}
    if (st === 'awaiting_confirmation') {{
      if (_scoutPollTimer) {{ clearInterval(_scoutPollTimer); _scoutPollTimer = null; }}
      _showConfirmPanel(data);
    }}
    if (st === 'done') {{
      if (_scoutPollTimer) {{ clearInterval(_scoutPollTimer); _scoutPollTimer = null; }}
      _showProgressPanel('完成', data.message || '调研完成！', 100);
      setTimeout(() => window.location.reload(), 2000);
    }}
    if (st === 'error') {{
      if (_scoutPollTimer) {{ clearInterval(_scoutPollTimer); _scoutPollTimer = null; }}
      document.getElementById('scoutProgressPanel').style.display = '';
      document.getElementById('scoutErrorMsg').style.display = '';
      document.getElementById('scoutErrorMsg').textContent = '错误：' + (data.message || '未知错误');
      document.getElementById('scoutFill').style.width = '0%';
      document.getElementById('scoutProgressMsg').textContent = '调研失败，请检查日志';
    }}
  }} catch (_) {{}}
}}

window.addEventListener('load', () => {{
  applyTheme();
  _pollScoutStatus();  // check if a scout is already running from a previous session
}});
</script>
</body>
</html>"""


def delete_topic_everything(*, topic: str = "", slug: str = "") -> dict:
    """Delete every artifact tied to one research theme.

    Clears papers.json entries for the topic, removes related directories
    (notes / pdfs / tmp / projects), removes chat history and logs, and
    regenerates the kanban. Returns counts of what was deleted so the
    front-end can confirm.
    """
    data = load_papers()
    papers = data.get("papers", [])
    searches = data.get("searches", [])

    if not slug and topic:
        slug = slugify_topic(topic)
    if not topic and slug:
        for s in searches:
            t = s.get("topic") or ""
            if slugify_topic(t) == slug:
                topic = t
                break
        if not topic:
            for p in papers:
                t = p.get("topic") or ""
                if slugify_topic(t) == slug:
                    topic = t
                    break

    removed_paper_ids: list[str] = []
    kept_papers = []
    for p in papers:
        if (
            (topic and p.get("topic") == topic)
            or (slug and slugify_topic(p.get("topic") or "") == slug)
        ):
            removed_paper_ids.append(p.get("id") or "")
        else:
            kept_papers.append(p)
    data["papers"] = kept_papers

    kept_searches = []
    removed_searches = 0
    for s in searches:
        s_topic = s.get("topic") or ""
        if (
            (topic and s_topic == topic)
            or (slug and slugify_topic(s_topic) == slug)
        ):
            removed_searches += 1
        else:
            kept_searches.append(s)
    data["searches"] = kept_searches
    data["last_updated"] = today_iso()
    save_papers(data)

    removed_dirs: list[str] = []
    dirs_to_remove = [
        os.path.join(NOTES_DIR, slug),
        os.path.join(PDFS_DIR, slug),
        os.path.join(PROJECTS_DIR, slug),
    ]
    tmp_root = os.path.join(OUTPUT_DIR, "tmp")
    for paper_id in removed_paper_ids:
        if paper_id:
            dirs_to_remove.append(os.path.join(tmp_root, paper_id))
    for d in dirs_to_remove:
        if d and os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            removed_dirs.append(d)

    removed_files: list[str] = []
    for paper_id in removed_paper_ids:
        if not paper_id:
            continue
        log_path = os.path.join(LOGS_DIR, f"{paper_id}.log")
        if os.path.isfile(log_path):
            try:
                os.unlink(log_path)
                removed_files.append(log_path)
            except OSError:
                pass

    if os.path.isdir(CHATS_DIR):
        for chat_file in os.listdir(CHATS_DIR):
            full = os.path.join(CHATS_DIR, chat_file)
            if not os.path.isfile(full):
                continue
            if (topic and topic in chat_file) or (slug and slug in chat_file):
                try:
                    os.unlink(full)
                    removed_files.append(full)
                except OSError:
                    pass

    try:
        regenerate_kanban()
    except Exception:
        pass

    return {
        "topic": topic,
        "slug": slug,
        "removed_papers": len(removed_paper_ids),
        "removed_searches": removed_searches,
        "removed_dirs": removed_dirs,
        "removed_files": removed_files,
    }


def regenerate_kanban():
    data = load_papers()
    papers = data.get("papers", [])
    searches = data.get("searches", [])
    # Always render Topic Navigator as the root page
    rendered = render_topic_index_html(searches, papers)
    with open(KANBAN_HTML, "w", encoding="utf-8") as f:
        f.write(rendered)

    # Also keep per-topic dashboard pages up to date (written to their own paths)
    for search in searches:
        topic = search.get("topic") or "Research Topic"
        slug = slugify_topic(topic)
        topic_papers = [p for p in papers if p.get("topic") == topic]
        year_range = search.get("year_range") or "Unknown Range"
        venues = search.get("venues") or "Unknown Venues"
        engineering_relpath = topic_engineering_relpath(slug)
        rendered = render_dashboard_html(
            active_topic=topic,
            active_year_range=year_range,
            active_venues=venues,
            engineering_link=f"/{engineering_relpath}",
            papers=topic_papers,
        )
        papers_file = topic_papers_abspath(slug)
        os.makedirs(os.path.dirname(papers_file), exist_ok=True)
        with open(papers_file, "w", encoding="utf-8") as f:
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
    papers_name = topic_papers_relpath(slug)
    engineering_name = topic_engineering_relpath(slug)
    papers_html = render_dashboard_html(
        active_topic=topic,
        active_year_range=year_range,
        active_venues=venues,
        engineering_link=f"/{engineering_name}",
        papers=topic_papers,
    )
    papers_file = os.path.join(OUTPUT_DIR, papers_name)
    os.makedirs(os.path.dirname(papers_file), exist_ok=True)
    with open(papers_file, "w", encoding="utf-8") as f:
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
        '<div class="lang-zh lang-block">当前还没有生成 engineering-scout 结果。运行 `engineering-scout` 后，这里会填入三层 ring 的工程实现、产品与部署信号。</div>'
        '<div class="lang-en lang-block">Engineering-scout has not generated results for this topic yet. Once it runs, this page will be populated with ring-based implementations, products, and deployment signals.</div>'
    )
    html = (
        template.replace("{{TOPIC}}", escape(topic))
        .replace("{{YEAR_RANGE}}", escape(year_range))
        .replace("{{LAST_UPDATED}}", escape(data.get("last_updated") or today_iso()))
        .replace("{{BACK_TO_PAPERS_LINK}}", "/kanban.html")
        .replace("{{AUTO_GENERATE_ENGINEERING}}", "true")
        .replace("{{READINESS_LEVEL}}", "pending")
        .replace("{{READINESS_EVIDENCE}}", placeholder)
        .replace("{{KEY_TAKEAWAY}}", placeholder)
        .replace("{{GAP_ANALYSIS}}", placeholder)
        .replace("{{RING1_ITEMS}}", '<div class="item"><div class="summary">No ring-1 results yet.</div></div>')
        .replace("{{RING2_ITEMS}}", '<div class="item"><div class="summary">No ring-2 results yet.</div></div>')
        .replace("{{RING3_ITEMS}}", '<div class="item"><div class="summary">No ring-3 results yet.</div></div>')
    )
    with open(ENGINEERING_HTML, "w", encoding="utf-8") as f:
        f.write(html)


def load_token_usage():
    return load_json_file(TOKEN_USAGE_JSON, {"operations": []})


def append_token_usage(op_type, entity_id, title, usage):
    if not usage:
        return
    data = load_token_usage()
    ops = data.get("operations") or []
    ops.append({
        "type": op_type,
        "entity_id": entity_id,
        "title": (title or "")[:80],
        "date": today_iso(),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cost_usd": round(float(usage.get("cost_usd") or 0), 6),
        "duration_ms": usage.get("duration_ms", 0),
    })
    data["operations"] = ops
    data["last_updated"] = today_iso()
    save_json_file(TOKEN_USAGE_JSON, data)


def parse_usage_from_log_file(log_path):
    """Scan log file in reverse for the final stream-json result event containing usage stats."""
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("type") == "result":
                    usage = obj.get("usage") or {}
                    return {
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cost_usd": obj.get("cost_usd", 0.0),
                        "duration_ms": obj.get("duration_ms", 0),
                    }
            except (json.JSONDecodeError, AttributeError):
                continue
    except OSError:
        pass
    return None


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


# ── Conference-Scout two-phase runner ──────────────────────────────────────

def load_scout_status():
    return load_json_file(
        SCOUT_STATUS_JSON,
        {
            "status": "idle",
            "topic": "",
            "slug": "",
            "description": "",
            "year_start": 2020,
            "year_end": 2026,
            "venue_group": "",
            "specific_venues": [],
            "message": "",
            "current_round": 0,
            "phase": 0,
            "last_updated": "",
            "candidates": [],
            "negative_patterns": [],
            "constraint_terms": [],
        },
    )


def save_scout_status(**kwargs):
    current = load_scout_status()
    current.update(kwargs)
    current["last_updated"] = today_iso()
    save_json_file(SCOUT_STATUS_JSON, current)


def _scout_tmp_dir(slug):
    return os.path.join(OUTPUT_DIR, "tmp", f"scout_{slug}")


def _candidates_path(slug):
    return os.path.join(_scout_tmp_dir(slug), "candidates_r4.json")


def _load_candidates(slug):
    return load_json_file(_candidates_path(slug), {})


def build_conference_scout_phase1_prompt(topic, description, year_start, year_end, venue_group, specific_venues):
    slug = slugify_topic(topic)
    venues_str = ", ".join(specific_venues) if specific_venues else f"(auto-select from venue_group: {venue_group})"
    today = today_iso()
    candidates_rel = f"output/tmp/scout_{slug}/candidates_r4.json"
    return (
        "Use the project skill `conference-scout` to search for papers.\n\n"
        "## Inputs\n"
        f"- topic: {topic}\n"
        f"- description: {description}\n"
        f"- year_start: {year_start}\n"
        f"- year_end: {year_end}\n"
        f"- venue_group: {venue_group}\n"
        f"- specific_venues: {venues_str}\n\n"
        "## IMPORTANT: Scope\n"
        "Run Rounds 0, 1, 2, 3, 4, and 4.5 ONLY.\n"
        "After Round 4.5, STOP. Do NOT begin Round 5 under any circumstances.\n"
        "The user will confirm via the web interface; a separate command will run Rounds 5-7.\n\n"
        "## Required output before stopping\n"
        f"Create directory `output/tmp/scout_{slug}/` and write the candidate list to:\n"
        f"  `{candidates_rel}`\n\n"
        "Use this JSON schema (fill with actual data):\n"
        "```json\n"
        "{\n"
        f'  "topic": "{topic}",\n'
        f'  "slug": "{slug}",\n'
        f'  "description": "{description}",\n'
        f'  "year_start": {year_start},\n'
        f'  "year_end": {year_end},\n'
        f'  "venue_group": "{venue_group}",\n'
        f'  "created": "{today}",\n'
        '  "negative_patterns": ["<from Round 2>"],\n'
        '  "constraint_terms": ["<from Round 2>"],\n'
        '  "candidates": [\n'
        '    {\n'
        '      "id": "<title-slugified>",\n'
        '      "title": "<full paper title>",\n'
        '      "authors": "<First Author et al.>",\n'
        '      "venue": "<venue name>",\n'
        '      "year": 2024,\n'
        '      "citations": 0,\n'
        '      "influential_citations": 0,\n'
        '      "pdf_available": "arXiv",\n'
        '      "arxiv_id": null,\n'
        '      "url": "https://..."\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "```\n\n"
        "After writing the file, display the Round 4.5 table exactly as in SKILL.md.\n"
        "Then output the line `SCOUT_PHASE1_COMPLETE` and STOP. Do not proceed to Round 5.\n"
    )


def build_conference_scout_phase2_prompt(topic, description, year_start, year_end, venue_group,
                                         confirmed_papers, negative_patterns, constraint_terms):
    slug = slugify_topic(topic)
    table = "| # | Title | Venue | Year | Citations | Influential |\n"
    table += "|---|-------|-------|------|-----------|-------------|\n"
    for i, p in enumerate(confirmed_papers, 1):
        table += (
            f"| {i} | {p.get('title', '')} | {p.get('venue', '')} "
            f"| {p.get('year', '')} | {p.get('citations', 0)} "
            f"| {p.get('influential_citations', 0)} |\n"
        )
    neg_str = ", ".join(negative_patterns) if negative_patterns else "(none)"
    const_str = ", ".join(constraint_terms) if constraint_terms else "(none)"
    return (
        "Continue the `conference-scout` process from Round 5. "
        "The user has confirmed the Round 4.5 candidate set via the web interface.\n\n"
        "## Context\n"
        f"- topic: {topic}\n"
        f"- description: {description}\n"
        f"- year_start: {year_start}\n"
        f"- year_end: {year_end}\n"
        f"- venue_group: {venue_group}\n"
        f"- negative_patterns: {neg_str}\n"
        f"- constraint_terms: {const_str}\n\n"
        "## Confirmed candidates from Round 4 (use these as the starting pool for Rounds 5-7)\n\n"
        f"{table}\n\n"
        "## Required actions\n"
        "Run Round 5 (Citation Expansion), Round 6 (Timeline Assembly), "
        "Round 6.5 (Token Usage), and Round 7 (Final Output) to completion.\n"
        f"Write output to `output/papers.json` and generate `output/projects/{slug}/papers.html`.\n"
        "Follow all instructions in the SKILL.md for these rounds.\n"
    )


def run_conference_scout_phase1_bg(topic, description, year_start, year_end, venue_group, specific_venues):
    slug = slugify_topic(topic)
    os.makedirs(_scout_tmp_dir(slug), exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"scout_{slug}_phase1.log")

    save_scout_status(
        topic=topic, slug=slug, description=description,
        year_start=year_start, year_end=year_end,
        venue_group=venue_group, specific_venues=specific_venues,
        status="running_phase1", phase=1, current_round=0,
        message="Round 0: 查询扩展中...", candidates=[],
    )

    prompt = build_conference_scout_phase1_prompt(
        topic, description, year_start, year_end, venue_group, specific_venues
    )
    cmd = [
        RESOLVED_CLAUDE_BIN, "-p", prompt,
        "--model", MODEL,
        "--permission-mode", "bypassPermissions",
        "--add-dir", ROOT,
        "--output-format", "stream-json",
        "--verbose",
    ]
    _round_msgs_p1 = {
        0: "Round 0: 查询扩展中...",
        1: "Round 1: 发现阶段 — 搜索综述论文...",
        2: "Round 2: 提取 Anchor 关键词...",
        3: "Round 3: 精确搜索中...",
        4: "Round 4: 相关性过滤中...",
        4.5: "Round 4.5: 整理候选列表...",
    }
    try:
        env = os.environ.copy()
        env["PATH"] = os.path.dirname(RESOLVED_CLAUDE_BIN) + os.pathsep + env.get("PATH", "")
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\nTopic: {topic}\nPhase: 1\n\n")
            lf.flush()
            proc = subprocess.Popen(
                cmd, cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            logs = []
            while proc.poll() is None:
                if proc.stdout:
                    ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if ready:
                        line = proc.stdout.readline()
                        if line:
                            s = line.rstrip()
                            lf.write(s + "\n"); lf.flush()
                            logs.append(s); logs = logs[-80:]
                            m = _ROUND_RE.search(s)
                            if m:
                                try:
                                    rn = float(m.group(1))
                                    save_scout_status(
                                        current_round=rn,
                                        message=_round_msgs_p1.get(rn, f"Round {rn}: 处理中...")
                                    )
                                except ValueError:
                                    pass
            rem = proc.stdout.read() if proc.stdout else ""
            for raw in rem.splitlines():
                lf.write(raw.rstrip() + "\n"); logs.append(raw.rstrip())
            lf.flush(); logs = logs[-80:]
            if proc.returncode not in (0, -15):
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"claude exited {proc.returncode}")

        cdata = _load_candidates(slug)
        candidates = cdata.get("candidates", [])
        if not cdata:
            raise RuntimeError("Phase 1 completed but candidates_r4.json was not written.")
        save_scout_status(
            status="awaiting_confirmation",
            current_round=4.5,
            message=f"Round 4.5 完成：{len(candidates)} 篇候选论文，请确认后继续 Round 5-7",
            candidates=candidates,
            negative_patterns=cdata.get("negative_patterns", []),
            constraint_terms=cdata.get("constraint_terms", []),
        )
        print(f"[serve.py] Scout Phase 1 done: {topic}, {len(candidates)} candidates", flush=True)
    except Exception as exc:
        save_scout_status(status="error", message=str(exc))
        print(f"[serve.py] Scout Phase 1 error: {exc}", flush=True)


def run_conference_scout_phase2_bg(topic, description, year_start, year_end, venue_group,
                                    confirmed_papers, negative_patterns, constraint_terms):
    slug = slugify_topic(topic)
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"scout_{slug}_phase2.log")

    save_scout_status(
        status="running_phase2", phase=2, current_round=5,
        message="Round 5: 引用扩展中...",
    )

    prompt = build_conference_scout_phase2_prompt(
        topic, description, year_start, year_end, venue_group,
        confirmed_papers, negative_patterns, constraint_terms
    )
    cmd = [
        RESOLVED_CLAUDE_BIN, "-p", prompt,
        "--model", MODEL,
        "--permission-mode", "bypassPermissions",
        "--add-dir", ROOT,
        "--output-format", "stream-json",
        "--verbose",
    ]
    _round_msgs_p2 = {
        5: "Round 5: 引用扩展中...",
        6: "Round 6: 组装时间线...",
        6.5: "Round 6.5: 记录 Token 用量...",
        7: "Round 7: 生成最终输出...",
    }
    try:
        env = os.environ.copy()
        env["PATH"] = os.path.dirname(RESOLVED_CLAUDE_BIN) + os.pathsep + env.get("PATH", "")
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\nTopic: {topic}\nPhase: 2\n\n")
            lf.flush()
            proc = subprocess.Popen(
                cmd, cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            logs = []
            while proc.poll() is None:
                if proc.stdout:
                    ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if ready:
                        line = proc.stdout.readline()
                        if line:
                            s = line.rstrip()
                            lf.write(s + "\n"); lf.flush()
                            logs.append(s); logs = logs[-80:]
                            m = _ROUND_RE.search(s)
                            if m:
                                try:
                                    rn = float(m.group(1))
                                    save_scout_status(
                                        current_round=rn,
                                        message=_round_msgs_p2.get(rn, f"Round {rn}: 处理中...")
                                    )
                                except ValueError:
                                    pass
            rem = proc.stdout.read() if proc.stdout else ""
            for raw in rem.splitlines():
                lf.write(raw.rstrip() + "\n"); logs.append(raw.rstrip())
            lf.flush(); logs = logs[-80:]
            if proc.returncode not in (0, -15):
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"claude exited {proc.returncode}")

        usage = parse_usage_from_log_file(log_path)
        append_token_usage("conference-scout", slug, topic, usage)
        save_scout_status(
            status="done", current_round=7,
            message="调研完成！新主题已添加到 Topic Navigator。",
        )
        regenerate_kanban()
        print(f"[serve.py] Scout Phase 2 done: {topic}", flush=True)
    except Exception as exc:
        save_scout_status(status="error", message=str(exc))
        print(f"[serve.py] Scout Phase 2 error: {exc}", flush=True)


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
        RESOLVED_CLAUDE_BIN,
        "-p",
        prompt,
        "--model",
        MODEL,
        "--permission-mode",
        "bypassPermissions",
        "--add-dir",
        ROOT,
        "--output-format",
        "stream-json",
        "--verbose",
    ]

    try:
        claude_dir = os.path.dirname(RESOLVED_CLAUDE_BIN)
        env = os.environ.copy()
        env["PATH"] = claude_dir + os.pathsep + env.get("PATH", "")
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
                    log_file.write("[serve.py] Engineering page exists and Claude CLI is idle; terminating process.\n")
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
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"claude exited {proc.returncode}")

        if not os.path.exists(ENGINEERING_HTML):
            raise RuntimeError("engineering-scout completed but did not create output/engineering.html")

        usage = parse_usage_from_log_file(log_path)
        append_token_usage("engineering-scout", slugify_topic(topic), topic, usage)
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
    slug = paper_topic_slug(paper)
    pid = paper["id"]
    new_layout = f"output/notes/{slug}/{pid}/note.md"
    if os.path.exists(os.path.join(ROOT, new_layout)):
        return new_layout
    legacy = f"output/notes/{slug}/{pid}.md"
    if os.path.exists(os.path.join(ROOT, legacy)):
        return legacy
    # Default to the new layout for new writes
    return new_layout


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
            paper["pipeline_step"] = ""
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
                    "status": "done",
                    "pipeline_status": "complete",
                    "pipeline_step": "",
                    "note_path": note_relpath,
                    "last_updated": today_iso(),
                }
            )
            break
    save_papers(data)
    ensure_local_pdf(paper_id)
    regenerate_kanban()
    return True


PAPER_READER_PYTHON = "/home/wangmingke/anaconda3/envs/derm-vlm/bin/python"


def build_paper_reader_prompt(url, paper_id, title):
    paper = find_paper_by_id(paper_id) or {}
    topic_slug = paper_topic_slug(paper) if paper else "unclassified"
    note_relpath = paper_note_relpath(paper_id)
    workdir = f"output/tmp/{paper_id}"
    prefix = paper_id.split("-")[0][:20] or "run"

    return f"""You are running the project skill `paper-reader` to deeply read ONE paper. Be efficient: this run is being driven from a button click on the HTML dashboard, not an interactive chat.

Paper URL: {url}
Paper ID: {paper_id}
Title: {title}
Topic slug: {topic_slug}

## Required reading (do NOT browse the whole repo)
Read these files once, then start executing:
1. `skills/paper-reader/SKILL.md` — the 15-step workflow
2. `references/pdf-cascade.md` — only if PDF acquisition fails

Do NOT `rg` / `find` the entire repository. Do not read TODO.md, README.md, or unrelated reference files unless a step explicitly blocks.

## Required Python interpreter

ALL pipeline scripts MUST be invoked with this interpreter (it has PyMuPDF installed):

    {PAPER_READER_PYTHON}

Do NOT use the bare `python` command — the system default is Python 3.8 without PyMuPDF and will fail at Step 4. Do not try to install PyMuPDF; use the interpreter above.

## Execution plan (follow this order, do not improvise)

Step A. Batch Steps 1-9 in one shot. Do not call resolve_paper.py / collect_metadata.py / fetch_pdf.py / extract_*.py individually:

    {PAPER_READER_PYTHON} skills/paper-reader/scripts/run_pipeline.py \\
      --input "{url}" \\
      --paper-id "{paper_id}" \\
      --topic-slug "{topic_slug}" \\
      --papers-json output/papers.json \\
      --prefix {prefix}

This produces `{workdir}/{prefix}_bundle.json` and the other artifacts. Read the bundle yourself to understand the paper.

Step B. Write `{workdir}/{prefix}_note.plan.json` — the note_plan artifact required by the SKILL.md grounding contract.

Step C. Run lint_grounding:

    {PAPER_READER_PYTHON} skills/paper-reader/scripts/lint_grounding.py \\
      --note-plan {workdir}/{prefix}_note.plan.json \\
      --source-manifest {workdir}/{prefix}_source_manifest.json \\
      --bundle-json {workdir}/{prefix}_bundle.json \\
      --figure-decisions {workdir}/{prefix}_figure_table_decisions.json

If it fails, fix the note_plan and re-run. Do NOT proceed until it passes.

Step D. Draft the Chinese 12-section note to `{workdir}/{prefix}_note.md`. Follow the template in `skills/paper-reader/assets/note_template.md`.

Step E. Lint the draft:

    {PAPER_READER_PYTHON} skills/paper-reader/scripts/lint_note.py \\
      --input {workdir}/{prefix}_note.md \\
      --plan-file {workdir}/{prefix}_note.plan.json

If `passes_style_gate: false` or `passes_basic_structure: false`, fix and re-lint. Maximum 3 lint cycles — if still failing after 3 attempts, write what you have and report the remaining issues.

Step F. Quality + readability review (in the same turn — do not pause for confirmation), then persist:

    {PAPER_READER_PYTHON} skills/paper-reader/scripts/write_note.py \\
      --title "{title}" \\
      --content-file {workdir}/{prefix}_note.md \\
      --lint-json {workdir}/{prefix}_note_lint.json \\
      --figure-decisions {workdir}/{prefix}_figure_table_decisions.json \\
      --topic-slug "{topic_slug}" \\
      --paper-id "{paper_id}" \\
      --papers-json output/papers.json \\
      --output {workdir}/{prefix}_write.json

`write_note.py` updates papers.json with `status=done`, `pipeline_status=complete`, `note_path`, `figures_dir`. It writes the note to `{note_relpath}`.

## Stop conditions

- After write_note.py succeeds, your task is complete. Print a one-line summary and STOP.
- Do not regenerate kanban.html — serve.py does that automatically.
- Do not edit unrelated files.
"""


def _get_pipeline_step_progress(paper_id):
    """Return (pct, 'zh|en') reflecting the most-recently-completed pipeline artifact."""
    prefix = (paper_id.split("-")[0] or "run")[:20]
    tmp_dir = os.path.join(OUTPUT_DIR, "tmp", paper_id)
    # Ordered most-advanced → least-advanced; first match wins
    steps = [
        (f"{prefix}_write.json",                  100, "笔记已完成|Note complete"),
        (f"{prefix}_note.md",                       94, "Claude 正在完善笔记...|Claude finalizing note..."),
        (f"{prefix}_note.plan.json",                88, "Claude 正在撰写笔记...|Claude writing note..."),
        (f"{prefix}_bundle.json",                   82, "Claude 正在规划笔记...|Claude planning note..."),
        (f"{prefix}_figure_table_decisions.json",   76, "正在构建分析包...|Building synthesis bundle..."),
        (f"{prefix}_figures.json",                  70, "正在规划图表决策...|Planning figure decisions..."),
        (f"{prefix}_assets.json",                   64, "正在规划图表...|Planning figures..."),
        (f"{prefix}_evidence.json",                 58, "正在提取图表资源...|Extracting figure assets..."),
        (f"{prefix}_source_manifest.json",          50, "正在提取证据...|Extracting evidence..."),
        (f"{prefix}_fetch.json",                    38, "正在提取正文...|Extracting source text..."),
        (f"{prefix}_metadata.json",                 24, "正在获取 PDF...|Fetching PDF..."),
        (f"{prefix}_resolve.json",                  16, "正在获取元数据...|Fetching metadata..."),
    ]
    if os.path.isdir(tmp_dir):
        existing = set(os.listdir(tmp_dir))
        for fname, pct, label in steps:
            if fname in existing:
                return pct, label
    return 10, "正在初始化...|Initializing..."


def read_paper_bg(paper_id, url, title):
    previous_state = snapshot_paper_state(paper_id)
    set_paper_fields(paper_id, progress=5, status="reading")
    regenerate_kanban()
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = paper_log_abspath(paper_id)

    prompt = build_paper_reader_prompt(url, paper_id, title)
    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", suffix=".txt", delete=False
    ) as output_file:
        output_path = output_file.name

    cmd = [
        RESOLVED_CLAUDE_BIN,
        "-p",
        prompt,
        "--model",
        MODEL,
        "--permission-mode",
        "bypassPermissions",
        "--add-dir",
        ROOT,
        "--output-format",
        "stream-json",
        "--verbose",
    ]

    try:
        if ensure_local_pdf(paper_id):
            set_paper_fields(paper_id, progress=8, status="reading")
            regenerate_kanban()

        claude_dir = os.path.dirname(RESOLVED_CLAUDE_BIN)
        env = os.environ.copy()
        env["PATH"] = claude_dir + os.pathsep + env.get("PATH", "")
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

            last_file_check = 0.0
            last_progress = 8
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

                # File-based progress: check every 2 seconds
                if now - last_file_check >= 2:
                    pct, label = _get_pipeline_step_progress(paper_id)
                    if pct != last_progress:
                        set_paper_fields(paper_id, progress=pct, status="reading",
                                         pipeline_step=label)
                        regenerate_kanban()
                        print(f"[serve.py] {paper_id}: {pct}% — {label.split('|')[0]}", flush=True)
                        last_progress = pct
                    last_file_check = now

                # Claude occasionally lingers after writing the note; treat long idle time as done.
                if os.path.exists(note_abspath) and now - last_output_at >= 20:
                    log_file.write("[serve.py] Note exists and Claude CLI is idle; terminating process.\n")
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
                raise RuntimeError("\n".join(logs[-20:]).strip() or f"claude exited {proc.returncode}")

        if not finalize_read_result(paper_id):
            last_message = "\n".join(logs[-10:]).strip()
            raise RuntimeError(
                "claude completed but did not create the expected note file"
                + (f"\n{last_message}" if last_message else "")
            )

        usage = parse_usage_from_log_file(log_path)
        append_token_usage("paper-reader", paper_id, title, usage)
        print(f"[serve.py] Complete via Claude CLI: {title[:60]}", flush=True)
    except Exception as exc:
        print(f"[serve.py] Claude CLI error: {exc}", flush=True)
        if _check_pdf_fetch_failed(paper_id):
            set_paper_fields(paper_id, status="reading", progress=5,
                             pipeline_status="pdf_fetch_failed")
            regenerate_kanban()
        else:
            restore_paper_state(paper_id, previous_state)
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

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
            html_file = os.path.normpath(os.path.join(OUTPUT_DIR, rel_name))
            output_root = os.path.normpath(OUTPUT_DIR)
            if html_file.startswith(output_root + os.sep) and os.path.exists(html_file):
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
                    "provider": "claude-cli",
                    "claude_bin": RESOLVED_CLAUDE_BIN,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/token-usage":
            data = load_token_usage()
            ops = data.get("operations") or []
            total_input = sum(o.get("input_tokens", 0) for o in ops)
            total_output = sum(o.get("output_tokens", 0) for o in ops)
            total_cache_read = sum(o.get("cache_read_input_tokens", 0) for o in ops)
            total_cost = round(sum(float(o.get("cost_usd") or 0) for o in ops), 4)
            body = json.dumps({
                "operations": ops,
                "totals": {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "cache_read_input_tokens": total_cache_read,
                    "total_tokens": total_input + total_output,
                    "cost_usd": total_cost,
                    "op_count": len(ops),
                },
                "last_updated": data.get("last_updated", ""),
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/scout-status":
            self.send_json(200, load_scout_status())

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

        elif path == "/api/chat-history":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            topic = (query.get("topic") or [""])[0].strip()
            page_type = (query.get("page_type") or ["papers"])[0].strip() or "papers"
            if not topic:
                self.send_json(400, {"ok": False, "error": "missing topic"})
                return
            history = load_chat_history(topic, page_type)
            self.send_json(200, history)

        elif path.startswith("/api/notes/"):
            tail = path[len("/api/notes/"):]
            # Figure asset route: /api/notes/{paper_id}/figures/{filename}
            if "/figures/" in tail:
                paper_id, _, fig_name = tail.partition("/figures/")
                fig_name = urllib.parse.unquote(fig_name)
                if not fig_name or "/" in fig_name or fig_name in {"..", "."}:
                    self.send_response(400)
                    self.send_cors()
                    self.end_headers()
                    return
                paper = find_paper_by_id(paper_id)
                figures_dir = paper.get("figures_dir") if paper else None
                if not figures_dir:
                    note_relpath = paper.get("note_path") if paper else None
                    if note_relpath:
                        figures_dir = os.path.join(os.path.dirname(note_relpath), "figures")
                fig_path = os.path.join(ROOT, figures_dir, fig_name) if figures_dir else ""
                if fig_path and os.path.isfile(fig_path):
                    body = open(fig_path, "rb").read()
                    ext = os.path.splitext(fig_name)[1].lower().lstrip(".")
                    content_type = {
                        "png": "image/png",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "gif": "image/gif",
                        "svg": "image/svg+xml",
                        "webp": "image/webp",
                    }.get(ext, "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_cors()
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.send_cors()
                    self.end_headers()
                return

            paper_id = tail
            paper = find_paper_by_id(paper_id)
            note_relpath = paper.get("note_path") if paper else None
            note_file = os.path.join(ROOT, note_relpath) if note_relpath else ""
            if os.path.exists(note_file):
                raw = open(note_file, "rb").read().decode("utf-8", errors="replace")
                # Rewrite figures/foo.png references so the browser fetches them via /api/notes
                quoted_pid = urllib.parse.quote(paper_id)
                rewritten = re.sub(
                    r"(!\[[^\]]*\]\()figures/",
                    lambda m: f"{m.group(1)}/api/notes/{quoted_pid}/figures/",
                    raw,
                )
                rewritten = re.sub(
                    r"(!\[\[)figures/",
                    lambda m: f"{m.group(1)}/api/notes/{quoted_pid}/figures/",
                    rewritten,
                )
                body = rewritten.encode("utf-8")
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
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return

            url = body.get("url", "").strip()
            paper_id = body.get("paper_id", "").strip()
            title = body.get("title", "").strip()

            if not url or not paper_id:
                self.send_json(400, {"ok": False, "error": "missing url or paper_id"})
                return

            threading.Thread(
                target=read_paper_bg,
                args=(paper_id, url, title),
                daemon=True,
            ).start()

            self.send_json(200, {"status": "started", "paper_id": paper_id})

        elif self.path == "/api/start-scout":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return
            topic = (body.get("topic") or "").strip()
            description = (body.get("description") or "").strip()
            year_start = int(body.get("year_start") or 2020)
            year_end = int(body.get("year_end") or datetime.now().year)
            venue_group = (body.get("venue_group") or "ai_ml").strip()
            specific_venues = [v.strip() for v in (body.get("specific_venues") or []) if str(v).strip()]
            if not topic:
                self.send_json(400, {"ok": False, "error": "missing topic"})
                return
            status = load_scout_status()
            if status.get("status") in ("running_phase1", "running_phase2"):
                self.send_json(409, {"ok": False, "error": "a scout is already running"})
                return
            threading.Thread(
                target=run_conference_scout_phase1_bg,
                args=(topic, description, year_start, year_end, venue_group, specific_venues),
                daemon=True,
            ).start()
            self.send_json(200, {"ok": True, "status": "started", "topic": topic})

        elif self.path == "/api/confirm-scout":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return
            confirmed_papers = body.get("confirmed_papers") or []
            negative_patterns = [s.strip() for s in (body.get("negative_patterns") or []) if str(s).strip()]
            constraint_terms = [s.strip() for s in (body.get("constraint_terms") or []) if str(s).strip()]
            if not confirmed_papers:
                self.send_json(400, {"ok": False, "error": "confirmed_papers is empty"})
                return
            status = load_scout_status()
            if status.get("status") != "awaiting_confirmation":
                self.send_json(409, {"ok": False, "error": "scout is not awaiting confirmation"})
                return
            topic = status.get("topic", "")
            description = status.get("description", "")
            year_start = int(status.get("year_start") or 2020)
            year_end = int(status.get("year_end") or datetime.now().year)
            venue_group = status.get("venue_group", "ai_ml")
            # Merge user-supplied adjustments into status
            save_scout_status(
                negative_patterns=negative_patterns,
                constraint_terms=constraint_terms,
            )
            threading.Thread(
                target=run_conference_scout_phase2_bg,
                args=(topic, description, year_start, year_end, venue_group,
                      confirmed_papers, negative_patterns, constraint_terms),
                daemon=True,
            ).start()
            self.send_json(200, {"ok": True, "status": "phase2_started"})

        elif self.path == "/api/readjust-scout":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return
            negative_patterns = [s.strip() for s in (body.get("negative_patterns") or []) if str(s).strip()]
            constraint_terms = [s.strip() for s in (body.get("constraint_terms") or []) if str(s).strip()]
            status = load_scout_status()
            if status.get("status") not in ("awaiting_confirmation", "error"):
                self.send_json(409, {"ok": False, "error": "scout is not in a re-adjustable state"})
                return
            topic = status.get("topic", "")
            description = status.get("description", "")
            year_start = int(status.get("year_start") or 2020)
            year_end = int(status.get("year_end") or datetime.now().year)
            venue_group = status.get("venue_group", "ai_ml")
            specific_venues = status.get("specific_venues") or []
            # Rebuild Phase 1 prompt with updated constraints injected into description
            extra = ""
            if negative_patterns:
                extra += f"\nAdjusted negative_patterns: {', '.join(negative_patterns)}"
            if constraint_terms:
                extra += f"\nAdjusted constraint_terms: {', '.join(constraint_terms)}"
            threading.Thread(
                target=run_conference_scout_phase1_bg,
                args=(topic, description + extra, year_start, year_end, venue_group, specific_venues),
                daemon=True,
            ).start()
            self.send_json(200, {"ok": True, "status": "readjust_started"})

        elif self.path == "/api/generate-engineering":
            started = maybe_start_engineering_generation(force=True)
            self.send_json(
                200,
                {
                    "status": "started" if started else "running",
                    "topic": latest_search_context()["topic"],
                },
            )

        elif self.path == "/api/delete-topic":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return
            topic = (body.get("topic") or "").strip()
            slug = (body.get("slug") or "").strip()
            if not topic and not slug:
                self.send_json(400, {"ok": False, "error": "missing topic or slug"})
                return
            try:
                result = delete_topic_everything(topic=topic, slug=slug)
                self.send_json(200, {"ok": True, **result})
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})

        elif self.path == "/api/clear-chat":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return
            topic = (body.get("topic") or "").strip()
            page_type = (body.get("page_type") or "papers").strip() or "papers"
            if not topic:
                self.send_json(400, {"ok": False, "error": "missing topic"})
                return
            save_chat_history(topic, page_type, [])
            self.send_json(200, {"ok": True, "messages": []})

        elif self.path.startswith("/api/upload-pdf"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            paper_id = (query.get("paper_id") or [""])[0].strip()
            if not paper_id:
                self.send_json(400, {"ok": False, "error": "missing paper_id"})
                return
            paper = find_paper_by_id(paper_id)
            if not paper:
                self.send_json(404, {"ok": False, "error": "paper not found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            if length == 0 or length > 100 * 1024 * 1024:
                self.send_json(400, {"ok": False, "error": "invalid content-length (0 or >100 MB)"})
                return
            pdf_data = self.rfile.read(length)
            if not pdf_data[:5] == b"%PDF-":
                self.send_json(400, {"ok": False, "error": "uploaded file is not a valid PDF"})
                return
            topic_slug = paper_topic_slug(paper)
            pdf_dir = os.path.join(PDFS_DIR, topic_slug)
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_relpath = f"output/pdfs/{topic_slug}/{paper_id}.pdf"
            pdf_abspath = os.path.join(ROOT, pdf_relpath)
            try:
                with open(pdf_abspath, "wb") as pf:
                    pf.write(pdf_data)
            except OSError as e:
                self.send_json(500, {"ok": False, "error": str(e)})
                return
            set_paper_fields(paper_id,
                             pdf_local_path=pdf_relpath,
                             pipeline_status="",
                             status="unread",
                             progress=0)
            regenerate_kanban()
            self.send_json(200, {"ok": True, "paper_id": paper_id, "pdf_path": pdf_relpath})

        elif self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self.send_json(400, {"ok": False, "error": "invalid json body"})
                return

            topic = (body.get("topic") or "").strip()
            page_type = (body.get("page_type") or "papers").strip() or "papers"
            message = (body.get("message") or "").strip()

            if not topic or not message:
                self.send_json(400, {"ok": False, "error": "missing topic or message"})
                return

            try:
                history_payload = load_chat_history(topic, page_type)
                history = history_payload.get("messages", [])
                history.append({"role": "user", "content": message, "time": datetime.now().isoformat(timespec="seconds")})
                answer = run_chat_query(topic, page_type, message, history)
                history.append({"role": "assistant", "content": answer, "time": datetime.now().isoformat(timespec="seconds")})
                save_chat_history(topic, page_type, history)
                response = {"ok": True, "reply": answer, "messages": history}
                self.send_json(200, response)
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})

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
    print("  Provider: Claude CLI")
    print(f"  Model: {MODEL}")
    print(f"  Claude binary: {RESOLVED_CLAUDE_BIN}")
    print("  Open http://localhost:5678/kanban.html")
    print("  Ctrl+C to stop\n")
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
