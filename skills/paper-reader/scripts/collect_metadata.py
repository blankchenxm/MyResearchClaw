#!/usr/bin/env python3
"""Collect and merge metadata from local papers.json plus Crossref/S2/OpenAlex/arXiv.

Adapted from DeepPaperNote's collect_metadata.py:
- Consults `output/papers.json` first when `--papers-json` is supplied. Existing
  record fields take precedence; only missing fields trigger network enrichment.
"""

from __future__ import annotations

from common import (
    base_parser,
    emit,
    enrich_metadata,
    maybe_load_json_record,
    paper_id_for_record,
    resolve_reference,
)
from resolve_paper import lookup_paper_in_papers_json


_REQUIRED_KEYS = ("title", "authors", "year", "venue", "doi", "arxiv_id", "abstract")


def _is_filled(record: dict, key: str) -> bool:
    value = record.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def main() -> None:
    p = base_parser(__doc__ or "collect metadata")
    p.add_argument(
        "--papers-json",
        default="",
        help="Path to output/papers.json. Existing record fields take precedence over the network.",
    )
    args = p.parse_args()

    if not args.input:
        raise SystemExit("collect_metadata.py requires --input.")

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
        record = resolve_reference(args.input)

    needs_enrichment = any(not _is_filled(record, k) for k in _REQUIRED_KEYS)
    if needs_enrichment:
        metadata = enrich_metadata(record)
    else:
        metadata = dict(record)

    if record_from_papers_json:
        for key, value in record_from_papers_json.items():
            if key == "id":
                continue
            if _is_filled(record_from_papers_json, key) and not _is_filled(metadata, key):
                metadata[key] = value

    metadata["paper_id"] = (
        args.paper_id
        or metadata.get("paper_id")
        or record_from_papers_json.get("id")
        or paper_id_for_record(metadata)
    )
    metadata["status"] = "ok"
    metadata["script"] = "collect_metadata.py"
    if record_from_papers_json:
        metadata["source"] = "papers_json"
    emit(metadata, args.output)


if __name__ == "__main__":
    main()
