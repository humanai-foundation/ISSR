"""Tests for the layout-aware PDF parser module.

Covers:
- pymupdf4llm primary parser
- Section heading detection
- Table extraction via pdfplumber
- Structured field extraction (CFDA, amounts, dates)
- pdfminer fallback path
"""

from pathlib import Path

import pytest

from foa_pipeline.parsing.pdf_parser import (
    ParsedPDF,
    _extract_sections,
    extract_structured_fields,
    parse_foa_pdf,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_pdf"


# ═══════════════════════════════════════════════
# End-to-end parse tests (require a real PDF)
# ═══════════════════════════════════════════════


@pytest.fixture
def sample_pdf():
    pdf = FIXTURE_DIR / "gsoc_proposal.pdf"
    if not pdf.exists():
        pytest.skip("No test PDF available in fixtures/sample_pdf/")
    return pdf


class TestParseFoaPdf:
    def test_returns_parsed_pdf(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert isinstance(result, ParsedPDF)

    def test_uses_pymupdf4llm(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert result.parse_method == "pymupdf4llm"

    def test_extracts_full_text(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert len(result.full_text_markdown) > 500
        assert result.page_count > 0

    def test_extracts_metadata(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert isinstance(result.metadata, dict)

    def test_sections_are_list(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert isinstance(result.sections, list)
        # Should have at least one section (fallback creates 'Full Document')
        assert len(result.sections) >= 1

    def test_tables_are_list(self, sample_pdf):
        result = parse_foa_pdf(sample_pdf)
        assert isinstance(result.tables, list)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_foa_pdf(Path("/nonexistent/path/fake.pdf"))


# ═══════════════════════════════════════════════
# Unit tests for section extraction (no PDF needed)
# ═══════════════════════════════════════════════


class TestExtractSections:
    def test_detects_description_heading(self):
        text = "## Program Description\nThis program funds climate research."
        sections = _extract_sections(text)
        types = [s.section_type for s in sections]
        assert "description" in types

    def test_detects_eligibility_heading(self):
        text = "## Eligibility Information\nUniversities may apply."
        sections = _extract_sections(text)
        types = [s.section_type for s in sections]
        assert "eligibility" in types

    def test_detects_dates_heading(self):
        text = "## Key Dates\nDeadline: September 30, 2025."
        sections = _extract_sections(text)
        types = [s.section_type for s in sections]
        assert "dates" in types

    def test_detects_budget_heading(self):
        text = "## Award Information\nUp to $500,000 per award."
        sections = _extract_sections(text)
        types = [s.section_type for s in sections]
        assert "budget" in types

    def test_multiple_sections(self):
        text = (
            "## Summary\nOverview text.\n"
            "## Eligibility\nWho may apply.\n"
            "## Key Dates\nDeadline info.\n"
        )
        sections = _extract_sections(text)
        assert len(sections) >= 3

    def test_fallback_single_section(self):
        text = "Just some plain text with no headings at all."
        sections = _extract_sections(text)
        assert len(sections) == 1
        assert sections[0].section_type == "description"
        assert sections[0].heading == "Full Document"

    def test_empty_text(self):
        sections = _extract_sections("")
        assert sections == []

    def test_section_content_extraction(self):
        text = "## Synopsis\nFirst paragraph.\nSecond paragraph."
        sections = _extract_sections(text)
        desc = [s for s in sections if s.section_type == "description"]
        assert len(desc) == 1
        assert "First paragraph" in desc[0].content


# ═══════════════════════════════════════════════
# Unit tests for structured field extraction
# ═══════════════════════════════════════════════


class TestExtractStructuredFields:
    def test_cfda_extraction(self):
        parsed = ParsedPDF(
            source_path="test.pdf",
            full_text_markdown="CFDA Number: 47.075 and also 93.103 are listed.",
            sections=[],
            tables=[],
            metadata={},
            page_count=1,
            parse_method="pymupdf4llm",
        )
        fields = extract_structured_fields(parsed)
        assert "cfda_numbers" in fields
        assert "47.075" in fields["cfda_numbers"]
        assert "93.103" in fields["cfda_numbers"]

    def test_award_amount_extraction(self):
        parsed = ParsedPDF(
            source_path="test.pdf",
            full_text_markdown="Awards range from $50,000 to $500,000.",
            sections=[],
            tables=[],
            metadata={},
            page_count=1,
            parse_method="pymupdf4llm",
        )
        fields = extract_structured_fields(parsed)
        assert fields.get("award_floor") == 50000.0
        assert fields.get("award_ceiling") == 500000.0

    def test_due_date_extraction(self):
        parsed = ParsedPDF(
            source_path="test.pdf",
            full_text_markdown="Deadline: September 30, 2025",
            sections=[],
            tables=[],
            metadata={},
            page_count=1,
            parse_method="pymupdf4llm",
        )
        fields = extract_structured_fields(parsed)
        assert "close_date_raw" in fields

    def test_no_fields_in_empty_text(self):
        parsed = ParsedPDF(
            source_path="test.pdf",
            full_text_markdown="",
            sections=[],
            tables=[],
            metadata={},
            page_count=0,
            parse_method="pymupdf4llm",
        )
        fields = extract_structured_fields(parsed)
        assert fields == {}
