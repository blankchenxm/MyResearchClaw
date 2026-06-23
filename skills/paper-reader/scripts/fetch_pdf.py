#!/usr/bin/env python3
"""Acquire the best available PDF for one paper via the MyResearchClaw cascade.

Adapted from DeepPaperNote's fetch_pdf.py. Cascade order:
1. Local PDF at output/pdfs/{topic_slug}/{paper_id}.pdf (when --local-pdf-dir is supplied).
2. arXiv direct URL (when arxiv_id is known).
3. S2 openAccessPdf URL (when known via record).
4. OpenAlex best_oa_location.pdf_url (when DOI is known).
5. Unpaywall best_oa_location.url_for_pdf (when DOI is known).
6. (Google Scholar / CDP step is left to higher-level fallback — see references/pdf-cascade.md.)

Writes `full_text_status`, `open_access_status`, and `pdf_url` into the JSON payload
so downstream stages and `output/papers.json` updates can use them.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path
from typing import Optional

from common import (
    default_pdf_path,
    emit,
    enrich_metadata,
    extract_doi,
    http_get_bytes,
    http_get_json,
    maybe_load_json_record,
    paper_id_for_record,
    resolve_reference,
    semantic_scholar_headers,
)
from resolve_paper import lookup_paper_in_papers_json


CONTACT_EMAIL_DEFAULT = "myresearchclaw@example.com"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__ or "fetch pdf")
    p.add_argument("--input", required=True, help="Metadata JSON path, JSON string, or raw paper reference.")
    p.add_argument("--output", default="", help="Output path for JSON status.")
    p.add_argument("--paper-id", default="", help="Canonical paper id if already known.")
    p.add_argument("--dest-dir", default="", help="Directory for downloaded PDFs.")
    p.add_argument(
        "--local-pdf-dir",
        default="",
        help="Pre-existing PDF directory (e.g. output/pdfs/{topic_slug}/). Checked first.",
    )
    p.add_argument(
        "--papers-json",
        default="",
        help="Path to output/papers.json. Look up known arxiv_id/doi/pdf_url before going to the network.",
    )
    p.add_argument(
        "--contact-email",
        default=CONTACT_EMAIL_DEFAULT,
        help="Contact email for OpenAlex/Unpaywall polite pool (default: placeholder).",
    )
    return p


def is_pdf_content(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]


def append_candidate(candidates: list[tuple[str, str]], kind: str, value: str) -> None:
    cleaned = (value or "").strip()
    if cleaned and (kind, cleaned) not in candidates:
        candidates.append((kind, cleaned))


def lookup_local_pdf(local_pdf_dir: str, paper_id: str) -> Optional[Path]:
    if not local_pdf_dir or not paper_id:
        return None
    base = Path(local_pdf_dir).expanduser().resolve()
    if not base.is_dir():
        return None
    direct = base / f"{paper_id}.pdf"
    if direct.is_file():
        return direct
    # Tolerate trailing year suffix or extra hyphen variants (e.g. `..._2018.pdf`).
    for candidate in sorted(base.glob("*.pdf")):
        stem = candidate.stem.lower()
        if stem.startswith(paper_id.lower()) or paper_id.lower() in stem:
            return candidate
    return None


def openalex_pdf_url(doi: str, email: str) -> tuple[str, str]:
    """Return (pdf_url, oa_status) from OpenAlex by DOI, or ("", "")."""
    if not doi:
        return ("", "")
    quoted = urllib.parse.quote(doi, safe="/")
    url = (
        "https://api.openalex.org/works?filter=doi:"
        f"{quoted}&select=id,open_access,best_oa_location&per-page=1&mailto={email}"
    )
    try:
        data = http_get_json(url)
    except Exception:
        return ("", "")
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        return ("", "")
    first = results[0] if isinstance(results[0], dict) else {}
    oa_status = str(((first.get("open_access") or {}).get("oa_status")) or "")
    loc = first.get("best_oa_location") or {}
    pdf_url = str(loc.get("pdf_url") or "")
    return (pdf_url, oa_status)


def semantic_scholar_pdf_url(doi: str) -> str:
    """Return openAccessPdf.url from S2 by DOI, or ""."""
    if not doi:
        return ""
    import urllib.parse as _up
    encoded = _up.quote(doi, safe="")
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{encoded}"
        "?fields=openAccessPdf,externalIds"
    )
    try:
        data = http_get_json(url, headers=semantic_scholar_headers())
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    oa = data.get("openAccessPdf") or {}
    return str(oa.get("url") or "") if isinstance(oa, dict) else ""


def unpaywall_pdf_url(doi: str, email: str) -> tuple[str, str]:
    """Return (pdf_url, oa_status) from Unpaywall by DOI, or ("", "")."""
    if not doi:
        return ("", "")
    quoted = urllib.parse.quote(doi, safe="/")
    url = f"https://api.unpaywall.org/v2/{quoted}?email={email}"
    try:
        data = http_get_json(url)
    except Exception:
        return ("", "")
    if not isinstance(data, dict):
        return ("", "")
    oa_status = str(data.get("oa_status") or "")
    loc = data.get("best_oa_location") or {}
    if not isinstance(loc, dict):
        return ("", oa_status)
    pdf_url = str(loc.get("url_for_pdf") or "")
    is_oa = bool(data.get("is_oa"))
    if not is_oa and not pdf_url:
        return ("", oa_status or "closed")
    return (pdf_url, oa_status)


def pdf_source_candidates(
    record: dict, *, contact_email: str = CONTACT_EMAIL_DEFAULT
) -> list[tuple[str, str]]:
    """Construct ordered candidate list following references/pdf-cascade.md."""
    candidates: list[tuple[str, str]] = []

    # Step 1: arXiv direct URL
    arxiv_id = str(record.get("arxiv_id", "") or "").strip()
    if arxiv_id:
        append_candidate(candidates, "arxiv", f"https://arxiv.org/pdf/{arxiv_id}")

    # Step 2: S2 openAccessPdf already on the record
    pdf_url = str(record.get("pdf_url", "") or "").strip()
    if pdf_url:
        append_candidate(candidates, "s2_open_access", pdf_url)

    source_url = str(record.get("source_url", "") or "").strip()
    if source_url.lower().endswith(".pdf"):
        append_candidate(candidates, "source_url_pdf", source_url)

    # Step 3 + 4: DOI-driven OpenAlex / Unpaywall
    doi = extract_doi(str(record.get("doi", "") or "").strip())
    if doi:
        oa_pdf, oa_status = openalex_pdf_url(doi, contact_email)
        if oa_pdf:
            append_candidate(candidates, "openalex", oa_pdf)
        if oa_status:
            record["open_access_status"] = oa_status

        unp_pdf, unp_status = unpaywall_pdf_url(doi, contact_email)
        if unp_pdf:
            append_candidate(candidates, "unpaywall", unp_pdf)
        if unp_status and not record.get("open_access_status"):
            record["open_access_status"] = unp_status

        # Step 5: Semantic Scholar openAccessPdf (covers cases where metadata came from
        # OpenAlex/Crossref and S2's open-access PDF was never populated into the record)
        s2_pdf = semantic_scholar_pdf_url(doi)
        if s2_pdf:
            append_candidate(candidates, "s2_openaccesspdf", s2_pdf)

    return candidates


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)

    record_from_papers_json = lookup_paper_in_papers_json(
        args.papers_json,
        paper_id=args.paper_id,
        input_ref=args.input,
    )

    input_record = maybe_load_json_record(args.input)
    if input_record is not None:
        record = dict(input_record)
    elif record_from_papers_json:
        record = dict(record_from_papers_json)
        record.setdefault("source_url", record.get("url", ""))
    else:
        record = enrich_metadata(resolve_reference(args.input))

    if record_from_papers_json:
        for key in ("arxiv_id", "doi", "pdf_url", "url", "title", "authors"):
            if record_from_papers_json.get(key) and not record.get(key):
                record[key] = record_from_papers_json.get(key)

    record["paper_id"] = (
        args.paper_id
        or record.get("paper_id")
        or record_from_papers_json.get("id")
        or paper_id_for_record(record)
    )

    # Step 0: pre-downloaded local PDF
    local_pdf = lookup_local_pdf(args.local_pdf_dir, record["paper_id"])
    if local_pdf is None:
        local_value = str(record.get("local_pdf_path", "") or "").strip()
        if local_value:
            candidate = Path(local_value).expanduser()
            if candidate.is_file():
                local_pdf = candidate.resolve()
    if local_pdf is not None:
        payload = {
            "status": "ok",
            "script": "fetch_pdf.py",
            "paper_id": record["paper_id"],
            "title": record.get("title", ""),
            "pdf_path": str(local_pdf),
            "pdf_source": "local_pdf",
            "source_url": record.get("source_url", "") or str(local_pdf),
            "pdf_url": "",
            "full_text_status": "open_pdf",
            "open_access_status": record.get("open_access_status", ""),
        }
        emit(payload, args.output)
        return

    candidates = pdf_source_candidates(record, contact_email=args.contact_email)
    if not candidates:
        payload = {
            "status": "error",
            "script": "fetch_pdf.py",
            "paper_id": record["paper_id"],
            "title": record.get("title", ""),
            "error": "No accessible PDF source found in cascade Step 1-4.",
            "source_url": record.get("source_url", ""),
            "full_text_status": _infer_no_pdf_status(record),
            "open_access_status": record.get("open_access_status", ""),
        }
        emit(payload, args.output)
        raise SystemExit(1)

    target_path = default_pdf_path(record, dest_dir=args.dest_dir)
    attempted_sources: list[dict[str, str]] = []
    downloaded: tuple[str, str, bytes] | None = None
    seen_html = False
    seen_blocked = False
    for candidate_kind, candidate_value in candidates:
        try:
            data = http_get_bytes(candidate_value)
        except Exception as exc:
            msg = str(exc)
            attempted_sources.append(
                {"kind": candidate_kind, "url": candidate_value, "status": f"download_error:{msg[:200]}"}
            )
            if "403" in msg or "cloudflare" in msg.lower() or "captcha" in msg.lower():
                seen_blocked = True
            continue
        if not is_pdf_content(data):
            attempted_sources.append(
                {"kind": candidate_kind, "url": candidate_value, "status": "not_pdf_content"}
            )
            seen_html = True
            continue
        downloaded = (candidate_kind, candidate_value, data)
        break

    if downloaded is None:
        if seen_blocked:
            full_text_status = "anti_bot_blocked"
        elif seen_html:
            full_text_status = "html_not_pdf"
        else:
            full_text_status = _infer_no_pdf_status(record)
        payload = {
            "status": "error",
            "script": "fetch_pdf.py",
            "paper_id": record["paper_id"],
            "title": record.get("title", ""),
            "error": "Cascade Step 1-4 returned no PDF content.",
            "source_url": record.get("source_url", ""),
            "attempted_sources": attempted_sources,
            "full_text_status": full_text_status,
            "open_access_status": record.get("open_access_status", ""),
        }
        emit(payload, args.output)
        raise SystemExit(1)

    source_kind, source_value, pdf_bytes = downloaded
    target_path.write_bytes(pdf_bytes)
    payload = {
        "status": "ok",
        "script": "fetch_pdf.py",
        "paper_id": record["paper_id"],
        "title": record.get("title", ""),
        "pdf_path": str(target_path),
        "pdf_source": source_kind,
        "source_url": record.get("source_url", ""),
        "pdf_url": source_value,
        "file_size": target_path.stat().st_size,
        "full_text_status": "open_pdf",
        "open_access_status": record.get("open_access_status", "")
        or _open_access_status_from_source(source_kind),
    }
    if attempted_sources:
        payload["attempted_sources"] = attempted_sources
    emit(payload, args.output)


def _open_access_status_from_source(source_kind: str) -> str:
    if source_kind == "arxiv":
        return "green"
    if source_kind in {"s2_open_access", "openalex", "unpaywall"}:
        return "unknown"
    return ""


def _infer_no_pdf_status(record: dict) -> str:
    oa = str(record.get("open_access_status", "") or "").lower()
    if oa == "closed":
        return "needs_institution"
    if oa in {"gold", "green", "hybrid", "bronze"}:
        return "no_open_pdf"
    return "unknown"


if __name__ == "__main__":
    main()
