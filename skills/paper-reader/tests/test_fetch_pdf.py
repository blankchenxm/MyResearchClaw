from __future__ import annotations

import json
from pathlib import Path

import pytest

import fetch_pdf


def test_pdf_source_candidates_prefers_arxiv_then_openalex_then_unpaywall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fetch_pdf.openalex_pdf_url",
        lambda doi, email: ("https://openalex.example/pdf", "gold"),
    )
    monkeypatch.setattr(
        "fetch_pdf.unpaywall_pdf_url",
        lambda doi, email: ("https://unpaywall.example/pdf", "green"),
    )
    candidates = fetch_pdf.pdf_source_candidates(
        {"arxiv_id": "1806.03346", "doi": "10.1145/3290605.3300376", "title": "AlterEgo"}
    )
    kinds = [kind for kind, _ in candidates]
    assert kinds[0] == "arxiv"
    assert "openalex" in kinds
    assert "unpaywall" in kinds
    assert ("arxiv", "https://arxiv.org/pdf/1806.03346") in candidates


def test_lookup_local_pdf_finds_paper_id_match(tmp_path: Path) -> None:
    pdf = tmp_path / "alterego_2018.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    found = fetch_pdf.lookup_local_pdf(str(tmp_path), "alterego")
    assert found is not None
    assert found.name == "alterego_2018.pdf"


def test_lookup_local_pdf_exact_paper_id_match(tmp_path: Path) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    found = fetch_pdf.lookup_local_pdf(str(tmp_path), "demo")
    assert found is not None
    assert found.name == "demo.pdf"


def test_lookup_local_pdf_no_match_returns_none(tmp_path: Path) -> None:
    found = fetch_pdf.lookup_local_pdf(str(tmp_path), "missing-id")
    assert found is None


def test_fetch_pdf_returns_local_pdf_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf = pdf_dir / "demo-paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    output = tmp_path / "fetch.json"

    fetch_pdf.main(
        [
            "--input",
            '{"arxiv_id":"1234.5678","title":"Demo"}',
            "--paper-id",
            "demo-paper",
            "--local-pdf-dir",
            str(pdf_dir),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text("utf-8"))
    assert payload["status"] == "ok"
    assert payload["pdf_source"] == "local_pdf"
    assert payload["full_text_status"] == "open_pdf"
    assert payload["pdf_path"].endswith("demo-paper.pdf")


def test_fetch_pdf_downloads_via_arxiv_when_no_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "fetch.json"
    requested: list[str] = []

    def fake_http_get_bytes(url: str) -> bytes:
        requested.append(url)
        if url == "https://arxiv.org/pdf/1806.03346":
            return b"%PDF-1.4\nbody"
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("fetch_pdf.http_get_bytes", fake_http_get_bytes)
    monkeypatch.setattr("fetch_pdf.openalex_pdf_url", lambda doi, email: ("", ""))
    monkeypatch.setattr("fetch_pdf.unpaywall_pdf_url", lambda doi, email: ("", ""))

    fetch_pdf.main(
        [
            "--input",
            '{"arxiv_id":"1806.03346","title":"AlterEgo"}',
            "--paper-id",
            "alterego",
            "--dest-dir",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )

    assert "https://arxiv.org/pdf/1806.03346" in requested
    payload = json.loads(output.read_text("utf-8"))
    assert payload["status"] == "ok"
    assert payload["pdf_source"] == "arxiv"
    assert payload["full_text_status"] == "open_pdf"
    assert payload["open_access_status"] == "green"


def test_fetch_pdf_fail_closed_sets_full_text_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "fetch.json"

    def fake_http_get_bytes(url: str) -> bytes:
        return b"<html>not a pdf</html>"

    monkeypatch.setattr("fetch_pdf.http_get_bytes", fake_http_get_bytes)
    monkeypatch.setattr("fetch_pdf.openalex_pdf_url", lambda doi, email: ("", ""))
    monkeypatch.setattr("fetch_pdf.unpaywall_pdf_url", lambda doi, email: ("", "closed"))

    with pytest.raises(SystemExit):
        fetch_pdf.main(
            [
                "--input",
                '{"doi":"10.1145/closed","title":"Closed"}',
                "--paper-id",
                "closed-paper",
                "--dest-dir",
                str(tmp_path),
                "--output",
                str(output),
            ]
        )

    payload = json.loads(output.read_text("utf-8"))
    assert payload["status"] == "error"
    assert payload["full_text_status"] in {"html_not_pdf", "no_open_pdf", "needs_institution"}
