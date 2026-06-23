#!/usr/bin/env python3
"""Write the final Markdown note into output/notes/{topic_slug}/{paper_id}/.

Adapted from DeepPaperNote's write_obsidian_note.py. Differences:
- No Obsidian vault / domain-routing logic. Caller supplies `--note-path` directly (or
  `--topic-slug` + `--paper-id` to derive the path under output/notes/).
- Figure asset materialization keeps DPN's safety rules but copies into
  `figures/` (not `images/`).
- Updates `output/papers.json` with `status`, `note_path`, `figures_dir`, and
  `pipeline_status` when `--papers-json` and `--paper-id` are supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from common import emit, ensure_parent, maybe_load_json_record


SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[2]
DEFAULT_NOTES_ROOT = REPO_ROOT / "output" / "notes"
DEFAULT_PAPERS_JSON = REPO_ROOT / "output" / "papers.json"
ASSET_SUBDIR = "figures"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__ or "write note")
    p.add_argument("--input", default="", help="Metadata JSON path or JSON string (for title fallback).")
    p.add_argument("--content-file", default="", help="Path to the final Markdown content.")
    p.add_argument("--content", default="", help="Inline Markdown content.")
    p.add_argument("--stdin", action="store_true", help="Read Markdown content from stdin.")
    p.add_argument(
        "--lint-json",
        default="",
        help="Lint JSON path. Refuse write if structure/style/math/figure/plan gate failed.",
    )
    p.add_argument(
        "--figure-decisions",
        default="",
        help="Figure/table decisions JSON. Insert decisions must reference materialized images.",
    )
    p.add_argument("--title", default="", help="Explicit title override.")
    p.add_argument("--output", default="", help="JSON status output path.")
    p.add_argument(
        "--note-path",
        default="",
        help="Absolute path to write note.md. Overrides --topic-slug/--paper-id derivation.",
    )
    p.add_argument(
        "--topic-slug",
        default="",
        help="Topic slug. Combined with --paper-id, writes to output/notes/{slug}/{paper_id}/note.md.",
    )
    p.add_argument("--paper-id", default="", help="Canonical paper id.")
    p.add_argument(
        "--papers-json",
        default="",
        help="Path to output/papers.json. When set, update status/note_path/figures_dir/pipeline_status.",
    )
    return p


def resolve_note_path(args: argparse.Namespace) -> Path:
    if args.note_path:
        return Path(args.note_path).expanduser().resolve()
    if args.topic_slug and args.paper_id:
        return (DEFAULT_NOTES_ROOT / args.topic_slug / args.paper_id / "note.md").resolve()
    raise SystemExit(
        "write_note.py requires --note-path, or both --topic-slug and --paper-id."
    )


def insert_decisions(decisions: dict) -> list[dict]:
    items = decisions.get("decisions", []) if isinstance(decisions, dict) else []
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("decision", "")).strip() == "insert"
    ]


def safe_image_filename(filename: str, source_image: Path) -> str:
    candidate = filename.strip() or source_image.name
    if (
        not candidate
        or candidate in {".", ".."}
        or "/" in candidate
        or "\\" in candidate
        or Path(candidate).is_absolute()
    ):
        raise SystemExit(f"Unsafe figure image filename in insert decision: {candidate}")
    return candidate


def embed_target_matches(target: str, expected_relative: str) -> bool:
    normalized = target.strip().strip("<>").split("|", 1)[0]
    if normalized == expected_relative:
        return True
    return normalized.endswith(f"/{expected_relative}")


def note_references_image_embed(note_text: str, expected_relative: str) -> bool:
    markdown_targets = re.findall(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", note_text)
    obsidian_targets = re.findall(r"!\[\[([^\]]+)\]\]", note_text)
    return any(
        embed_target_matches(target, expected_relative)
        for target in markdown_targets + obsidian_targets
    )


def materialize_insert_decisions(
    note_text: str,
    target_path: Path,
    decisions: dict,
    asset_subdir: str,
) -> list[dict]:
    materialized: list[dict] = []
    asset_dir = target_path.parent / asset_subdir
    for item in insert_decisions(decisions):
        source_value = str(item.get("source_image_path", "")).strip()
        source_image = Path(source_value).expanduser()
        if not source_value or not source_image.is_file():
            label = item.get("source_id") or item.get("label") or item.get("item_id") or "unknown"
            raise SystemExit(f"Insert decision source image does not exist for {label}: {source_value}")
        filename = safe_image_filename(
            str(item.get("source_image_filename", "")),
            source_image,
        )
        expected_relative = f"{asset_subdir}/{filename}"
        if not note_references_image_embed(note_text, expected_relative):
            label = item.get("source_id") or item.get("label") or item.get("item_id") or filename
            raise SystemExit(
                f"Insert decision for {label} is not referenced as an image embed: {expected_relative}."
            )
        asset_dir.mkdir(parents=True, exist_ok=True)
        dest_image = asset_dir / filename
        if dest_image.resolve().parent != asset_dir.resolve():
            raise SystemExit(f"Unsafe figure image destination: {dest_image}")
        if source_image.resolve() != dest_image.resolve():
            shutil.copy2(source_image, dest_image)
        materialized.append(
            {
                "source_id": item.get("source_id") or item.get("label") or item.get("item_id") or "",
                "source_image": str(source_image.resolve()),
                "dest_image_path": str(dest_image),
                "relative_markdown_path": expected_relative,
            }
        )
    return materialized


def update_papers_json(
    papers_json_path: Path,
    paper_id: str,
    note_path: Path,
    figures_dir: Path,
) -> bool:
    """Update the matching paper entry in papers.json. Return True if updated."""
    if not papers_json_path.is_file() or not paper_id:
        return False
    try:
        data = json.loads(papers_json_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    papers = data.get("papers", [])
    if not isinstance(papers, list):
        return False
    updated = False
    for entry in papers:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id", "")).strip() == paper_id:
            entry["status"] = "done"
            entry["progress"] = 100
            entry["note_path"] = str(note_path)
            entry["figures_dir"] = str(figures_dir)
            entry["pipeline_status"] = "complete"
            updated = True
            break
    if updated:
        papers_json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return updated


def main() -> None:
    args = parser().parse_args()

    record = maybe_load_json_record(args.input) or {}
    title = args.title or str(record.get("title", "")).strip()
    if not title:
        raise SystemExit("write_note.py requires --title or metadata with a title.")

    if args.lint_json:
        lint = json.loads(Path(args.lint_json).expanduser().resolve().read_text(encoding="utf-8"))
        if not lint.get("passes_basic_structure", False):
            raise SystemExit("write_note.py refused to write note because basic structure lint failed.")
        if not lint.get("passes_style_gate", False):
            raise SystemExit("write_note.py refused to write note because style gate failed.")
        if not lint.get("passes_math_gate", False):
            raise SystemExit("write_note.py refused to write note because math gate failed.")
        if "passes_figure_gate" in lint and not lint.get("passes_figure_gate", False):
            raise SystemExit("write_note.py refused to write note because figure gate failed.")
        if "passes_plan_gate" in lint and not lint.get("passes_plan_gate", False):
            raise SystemExit("write_note.py refused to write note because plan gate failed.")
        if "passes_substantive_content" in lint and not lint.get("passes_substantive_content", False):
            raise SystemExit(
                "write_note.py refused to write note because substantive content gate failed."
            )

    if args.content_file:
        note_text = Path(args.content_file).expanduser().resolve().read_text(encoding="utf-8")
    elif args.content:
        note_text = args.content
    elif args.stdin:
        note_text = sys.stdin.read()
    else:
        raise SystemExit("write_note.py requires --content-file, --content, or --stdin.")

    target_path = resolve_note_path(args)
    ensure_parent(target_path)
    asset_dir = target_path.parent / ASSET_SUBDIR

    figure_decisions = maybe_load_json_record(args.figure_decisions) if args.figure_decisions else {}
    if args.figure_decisions and figure_decisions is None:
        raise SystemExit(f"Expected JSON object for --figure-decisions: {args.figure_decisions}")
    materialized_figures = (
        materialize_insert_decisions(
            note_text,
            target_path,
            figure_decisions,
            ASSET_SUBDIR,
        )
        if figure_decisions
        else []
    )
    target_path.write_text(note_text, encoding="utf-8")
    asset_dir.mkdir(parents=True, exist_ok=True)

    paper_id = args.paper_id or str(record.get("paper_id", ""))
    papers_updated = False
    if args.papers_json:
        papers_updated = update_papers_json(
            Path(args.papers_json).expanduser().resolve(),
            paper_id,
            target_path,
            asset_dir,
        )

    payload = {
        "status": "ok",
        "script": "write_note.py",
        "paper_id": paper_id,
        "title": title,
        "note_path": str(target_path),
        "figures_dir": str(asset_dir),
        "materialized_figures": materialized_figures,
        "papers_json_updated": papers_updated,
    }
    emit(payload, args.output)


if __name__ == "__main__":
    main()
