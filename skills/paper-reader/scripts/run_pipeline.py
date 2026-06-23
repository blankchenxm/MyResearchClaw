#!/usr/bin/env python3
"""Run the deterministic paper-reader pipeline sequentially for one paper.

Adapted from DeepPaperNote's run_pipeline.py. Differences:
- Default workdir resolves to `output/tmp/{paper_id}/` under the MyResearchClaw repo root.
- Adds `--topic-slug` and `--paper-id` so the workdir layout matches MyResearchClaw conventions.
- Adds `--papers-json` and `--pdf-dir` so fetch_pdf.py can consult existing records first.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[2]  # paper-reader/scripts -> paper-reader -> skills -> repo root
DEFAULT_PAPERS_JSON = REPO_ROOT / "output" / "papers.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output"


# Known Python interpreters that have PyMuPDF installed. The pipeline silently
# switches to the first one available if the current interpreter lacks fitz,
# instead of failing at Step 4 with a cryptic ImportError.
PYMUPDF_CAPABLE_PYTHONS = (
    "/home/wangmingke/anaconda3/envs/derm-vlm/bin/python",
    "/home/meng/miniconda3/envs/agent/bin/python",
)


def resolve_python_with_fitz() -> str:
    """Return absolute path to a Python interpreter that has PyMuPDF (`fitz`).

    Falls back to sys.executable if neither the current interpreter nor any
    known fallback has it — the failure will then surface at extract_source_text.py
    with the helpful error already raised there.
    """
    if importlib.util.find_spec("fitz") is not None:
        return sys.executable
    if os.environ.get("MYRESEARCHCLAW_NO_AUTO_SWITCH"):
        return sys.executable
    for candidate in PYMUPDF_CAPABLE_PYTHONS:
        if not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "import fitz"],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            continue
        if result.returncode == 0:
            return candidate
    return sys.executable


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__ or "run pipeline")
    p.add_argument(
        "--input",
        required=True,
        help="Paper title, DOI, URL, arXiv id, local PDF path, or JSON artifact path.",
    )
    p.add_argument(
        "--workdir",
        default="",
        help="Directory for intermediate artifacts. Defaults to output/tmp/{paper_id}/.",
    )
    p.add_argument("--prefix", default="run", help="Filename prefix for artifacts.")
    p.add_argument(
        "--paper-id",
        default="",
        help="Canonical paper id (matches output/papers.json id field). If omitted, --workdir must be supplied.",
    )
    p.add_argument(
        "--topic-slug",
        default="",
        help="Topic slug used to locate the local PDF under output/pdfs/{topic_slug}/.",
    )
    p.add_argument(
        "--papers-json",
        default=str(DEFAULT_PAPERS_JSON),
        help="Path to output/papers.json for record-aware resolve/metadata/fetch.",
    )
    p.add_argument(
        "--pdf-dir",
        default="",
        help="Directory holding pre-downloaded PDFs. Defaults to output/pdfs/{topic_slug}/.",
    )
    return p


def run_step(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parser().parse_args()
    scripts_dir = SCRIPTS_DIR

    if args.workdir:
        workdir = Path(args.workdir).expanduser().resolve()
    elif args.paper_id:
        workdir = DEFAULT_OUTPUT_ROOT / "tmp" / args.paper_id
    else:
        raise SystemExit("run_pipeline.py requires --workdir or --paper-id.")
    workdir.mkdir(parents=True, exist_ok=True)

    pdf_dir = ""
    if args.pdf_dir:
        pdf_dir = str(Path(args.pdf_dir).expanduser().resolve())
    elif args.topic_slug:
        pdf_dir = str(DEFAULT_OUTPUT_ROOT / "pdfs" / args.topic_slug)

    resolve_json = workdir / f"{args.prefix}_resolve.json"
    metadata_json = workdir / f"{args.prefix}_metadata.json"
    fetch_json = workdir / f"{args.prefix}_fetch.json"
    source_manifest_json = workdir / f"{args.prefix}_source_manifest.json"
    raw_sections_jsonl = workdir / f"{args.prefix}_raw_sections.jsonl"
    full_text_md = workdir / f"{args.prefix}_full_text.md"
    evidence_json = workdir / f"{args.prefix}_evidence.json"
    assets_json = workdir / f"{args.prefix}_assets.json"
    figures_json = workdir / f"{args.prefix}_figures.json"
    figure_decisions_json = workdir / f"{args.prefix}_figure_table_decisions.json"
    bundle_json = workdir / f"{args.prefix}_bundle.json"

    py = resolve_python_with_fitz()
    if py != sys.executable:
        print(
            f"[run_pipeline.py] switching interpreter to {py} (current {sys.executable} lacks PyMuPDF)",
            file=sys.stderr,
        )

    def papers_json_args() -> list[str]:
        return ["--papers-json", args.papers_json] if args.papers_json else []

    resolve_cmd = [
        py,
        str(scripts_dir / "resolve_paper.py"),
        "--input",
        args.input,
        "--output",
        str(resolve_json),
        *papers_json_args(),
    ]
    if args.paper_id:
        resolve_cmd.extend(["--paper-id", args.paper_id])
    run_step(resolve_cmd)

    metadata_cmd = [
        py,
        str(scripts_dir / "collect_metadata.py"),
        "--input",
        args.input,
        "--output",
        str(metadata_json),
        *papers_json_args(),
    ]
    if args.paper_id:
        metadata_cmd.extend(["--paper-id", args.paper_id])
    run_step(metadata_cmd)

    fetch_cmd = [
        py,
        str(scripts_dir / "fetch_pdf.py"),
        "--input",
        args.input,
        "--output",
        str(fetch_json),
        *papers_json_args(),
    ]
    if args.paper_id:
        fetch_cmd.extend(["--paper-id", args.paper_id])
    if pdf_dir:
        fetch_cmd.extend(["--local-pdf-dir", pdf_dir])
    run_step(fetch_cmd)

    run_step(
        [
            py,
            str(scripts_dir / "extract_source_text.py"),
            "--input",
            str(fetch_json),
            "--output",
            str(source_manifest_json),
            "--raw-sections-output",
            str(raw_sections_jsonl),
            "--full-text-output",
            str(full_text_md),
        ]
    )
    run_step(
        [
            py,
            str(scripts_dir / "extract_evidence.py"),
            "--input",
            str(fetch_json),
            "--output",
            str(evidence_json),
        ]
    )
    run_step(
        [
            py,
            str(scripts_dir / "extract_pdf_assets.py"),
            "--input",
            str(fetch_json),
            "--output",
            str(assets_json),
        ]
    )
    run_step(
        [
            py,
            str(scripts_dir / "plan_figures.py"),
            "--evidence",
            str(evidence_json),
            "--assets",
            str(assets_json),
            "--output",
            str(figures_json),
        ]
    )
    run_step(
        [
            py,
            str(scripts_dir / "plan_figure_table_decisions.py"),
            "--source-manifest",
            str(source_manifest_json),
            "--figures",
            str(figures_json),
            "--assets",
            str(assets_json),
            "--output",
            str(figure_decisions_json),
        ]
    )
    run_step(
        [
            py,
            str(scripts_dir / "build_synthesis_bundle.py"),
            "--metadata",
            str(metadata_json),
            "--evidence",
            str(evidence_json),
            "--figures",
            str(figures_json),
            "--assets",
            str(assets_json),
            "--source-manifest",
            str(source_manifest_json),
            "--figure-decisions",
            str(figure_decisions_json),
            "--output",
            str(bundle_json),
        ]
    )

    print(
        "\n".join(
            [
                f"workdir={workdir}",
                f"resolve={resolve_json}",
                f"metadata={metadata_json}",
                f"fetch={fetch_json}",
                f"source_manifest={source_manifest_json}",
                f"raw_sections={raw_sections_jsonl}",
                f"full_text_md={full_text_md}",
                f"evidence={evidence_json}",
                f"assets={assets_json}",
                f"figures={figures_json}",
                f"figure_table_decisions={figure_decisions_json}",
                f"bundle={bundle_json}",
            ]
        )
    )


if __name__ == "__main__":
    main()
