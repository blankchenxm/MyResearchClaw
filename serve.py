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
PROJECTS_DIR = os.path.join(OUTPUT_DIR, "projects")
PAPERS_JSON = os.path.join(OUTPUT_DIR, "papers.json")
NOTES_DIR = os.path.join(OUTPUT_DIR, "notes")
PDFS_DIR = os.path.join(OUTPUT_DIR, "pdfs")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
CHATS_DIR = os.path.join(OUTPUT_DIR, "chats")
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
    prompt = f"""You are the embedded assistant for a MyResearchClaw project page.

Page topic: {topic}
Page type: {page_type}

You already know the current project context below. Use it as primary context. You may also use web search when needed for the user's question because this project allows Codex network search.

Project context:
{context}

Conversation so far:
{history_block}

User question:
{message}

Instructions:
- Answer directly and concretely.
- Prefer using the current project context first.
- If the user asks for clarification, comparison, synthesis, or follow-up reasoning, keep the answer tied to this project.
- If web search is useful, use it.
- Keep answers concise but informative.
"""

    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".txt", delete=False) as output_file:
        output_path = output_file.name

    cmd = [
        RESOLVED_CODEX_BIN,
        "--search",
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

    codex_dir = os.path.dirname(RESOLVED_CODEX_BIN)
    env = os.environ.copy()
    env["PATH"] = codex_dir + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=240,
        )
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n"
                f"Topic: {topic}\nPage type: {page_type}\nUser: {message}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Output:\n{proc.stdout}\n"
            )
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout.strip() or f"codex exited {proc.returncode}")
        try:
            with open(output_path, encoding="utf-8") as f:
                answer = f.read().strip()
        except OSError:
            answer = ""
        if not answer:
            answer = proc.stdout.strip()
        return answer.strip()
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


def render_progress_state(paper):
    progress = int(paper.get("progress") or 0)
    status = (paper.get("status") or "").strip()
    note_path = paper.get("note_path")

    fill_class = "progress-fill"
    label_class = "progress-label"
    label_html = ""

    if status == "done" or progress >= 100:
        fill_class += " done"
        label_class += " done"
        label_html = render_lang_inline("✓ 已完成", "✓ Complete")
    elif progress > 0 or status == "reading":
        fill_class += " active"
        label_html = render_lang_inline(f"精读中... {progress}%", f"Reading... {progress}%")

    if status == "done":
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

    return f"""
      <!-- ── Paper {idx} ── -->
      <div class="{status_card_class(paper)}" data-id="{escape(paper["id"])}" data-url="{paper_url}" data-pdf-url="{pdf_url}" data-progress="{progress}">
        <div class="card-header">
          <div class="card-title"><a href="{paper_url}" target="_blank">{title}</a></div>
          <span class="citations {citations_class}">{citations_text}</span>
        </div>
        <div class="card-role-row">
          <span class="timeline-role {role_css}">{escape(role_label)}</span>
          <span class="card-role-reason">{render_lang_inline(role_reason_zh[:180], role_reason_en[:180])}</span>
        </div>
        <div class="card-authors">{authors}</div>
        <div class="card-meta">
          <span class="{venue_class}">{escape(venue_text)}</span>{tags_block}
        </div>
        <div class="summary-block">
          <div class="summary-label">{render_lang_inline("摘要", "Summary")}</div>
          {render_lang_html(summary_zh, summary_en, tag="div", class_name="summary-copy")}
        </div>
        <div class="progress-row">
          <div class="progress-track"><div class="{fill_class}" style="width:{progress}%"></div></div>
          <span class="{label_class}">{label_html}</span>
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
            <a href="/projects/{row["slug"]}/papers.html">Open Papers →</a>
            <a href="/projects/{row["slug"]}/engineering.html">Engineering View →</a>
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
.lang-toggle {{
  position:fixed; top:64px; right:16px; z-index:9999; width:40px; height:40px; border-radius:50%;
  border:1px solid var(--line); background:var(--panel); color:var(--text); cursor:pointer; font:700 11px 'JetBrains Mono', monospace;
}}
.lang-block {{ display:block; }}
.lang-inline {{ display:inline; }}
.lang-en {{ display:none; }}
body.lang-en .lang-zh {{ display:none !important; }}
body.lang-en .lang-en.lang-block {{ display:block; }}
body.lang-en .lang-en.lang-inline {{ display:inline; }}
body:not(.lang-en) .lang-zh.lang-block {{ display:block; }}
body:not(.lang-en) .lang-zh.lang-inline {{ display:inline; }}
body:not(.lang-en) .lang-en {{ display:none !important; }}
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
  <button class="lang-toggle" onclick="toggleLanguage()" title="Toggle language">中/EN</button>
  <div class="wrap">
    <section class="hero">
      <div class="hero-eyebrow">MyResearchClaw</div>
      <h1>
        <span class="lang-zh lang-inline">Topic Navigator</span>
        <span class="lang-en lang-inline">Topic Navigator</span>
      </h1>
      <p>
        <span class="lang-zh lang-block">所有主题页面现在都收纳在 <code>output/projects/&lt;topic-slug&gt;/</code> 下。先进入对应的 Papers 页面，再在页面顶部点击 Engineering View；精读笔记仍会按主题写入 <code>output/notes/&lt;topic-slug&gt;/</code>。</span>
        <span class="lang-en lang-block">All topic pages now live under <code>output/projects/&lt;topic-slug&gt;/</code>. Open the corresponding Papers page first, then use the Engineering View button at the top; reading notes are still stored under <code>output/notes/&lt;topic-slug&gt;/</code>.</span>
      </p>
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
function applyLanguage() {{
  const isEn = localStorage.getItem('ui-lang') === 'en';
  document.body.classList.toggle('lang-en', isEn);
  document.querySelector('.lang-toggle').textContent = isEn ? 'EN' : '中';
}}
function toggleLanguage() {{
  const isEn = !(localStorage.getItem('ui-lang') === 'en');
  localStorage.setItem('ui-lang', isEn ? 'en' : 'zh');
  applyLanguage();
}}
function toggleTheme() {{
  const light = !document.body.classList.contains('light');
  localStorage.setItem('theme', light ? 'light' : 'dark');
  applyTheme();
}}
window.addEventListener('load', () => {{ applyTheme(); applyLanguage(); }});
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
        "--search",
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

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)

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

        elif self.path == "/api/generate-engineering":
            started = maybe_start_engineering_generation(force=True)
            self.send_json(
                200,
                {
                    "status": "started" if started else "running",
                    "topic": latest_search_context()["topic"],
                },
            )

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
