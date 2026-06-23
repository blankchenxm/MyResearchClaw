#!/usr/bin/env python3
"""Resolve a title, DOI, URL, arXiv ID, or local PDF into one paper identity.

Adapted from DeepPaperNote's resolve_paper.py:
- Consults `output/papers.json` first when `--papers-json` is supplied.
- If the input matches an existing record (by paper id, url, arxiv_id, or doi),
  return the record directly instead of going to the network.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import (
    base_parser,
    emit,
    extract_arxiv_id,
    extract_doi,
    maybe_load_json_record,
    paper_id_for_record,
    resolve_reference,
)


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def lookup_paper_in_papers_json(
    papers_json_path: str,
    *,
    paper_id: str = "",
    input_ref: str = "",
) -> dict:
    """Return the matching paper dict from output/papers.json, or {}."""
    if not papers_json_path:
        return {}
    try:
        data = json.loads(
            Path(papers_json_path).expanduser().resolve().read_text(encoding="utf-8")
        )
    except Exception:
        return {}
    papers = data.get("papers", [])
    if not isinstance(papers, list):
        return {}

    pid_norm = _normalize(paper_id)
    if pid_norm:
        for entry in papers:
            if isinstance(entry, dict) and _normalize(entry.get("id", "")) == pid_norm:
                return dict(entry)

    ref = _normalize(input_ref)
    if not ref:
        return {}

    arxiv_from_ref = (extract_arxiv_id(input_ref) or "").lower()
    doi_from_ref = (extract_doi(input_ref) or "").lower()

    for entry in papers:
        if not isinstance(entry, dict):
            continue
        url = _normalize(entry.get("url", ""))
        ax = _normalize(entry.get("arxiv_id", ""))
        doi = _normalize(entry.get("doi", ""))
        if url and (url == ref or url in ref or ref in url):
            return dict(entry)
        if ax and (ax == ref or (arxiv_from_ref and ax == arxiv_from_ref)):
            return dict(entry)
        if doi and (doi == ref or (doi_from_ref and doi == doi_from_ref)):
            return dict(entry)
    return {}


def main() -> None:
    p = base_parser(__doc__ or "resolve paper")
    p.add_argument(
        "--papers-json",
        default="",
        help="Path to output/papers.json. When set, look up existing records before going to the network.",
    )
    args = p.parse_args()

    if not args.input:
        raise SystemExit("resolve_paper.py requires --input.")

    record_from_papers_json = lookup_paper_in_papers_json(
        args.papers_json,
        paper_id=args.paper_id,
        input_ref=args.input,
    )

    input_record = maybe_load_json_record(args.input)
    if input_record is not None:
        resolved = dict(input_record)
    elif record_from_papers_json:
        resolved = dict(record_from_papers_json)
        resolved.setdefault("source_url", resolved.get("url", ""))
        resolved.setdefault("paper_id", record_from_papers_json.get("id", ""))
    else:
        resolved = resolve_reference(args.input)

    if record_from_papers_json:
        for key, value in record_from_papers_json.items():
            if key in {"id"}:
                continue
            if not resolved.get(key):
                resolved[key] = value

    resolved["paper_id"] = (
        args.paper_id
        or resolved.get("paper_id")
        or record_from_papers_json.get("id")
        or paper_id_for_record(resolved)
    )
    resolved["status"] = resolved.get("status") or "ok"
    resolved["script"] = "resolve_paper.py"
    if record_from_papers_json:
        resolved["source"] = "papers_json"
    emit(resolved, args.output)


if __name__ == "__main__":
    main()
