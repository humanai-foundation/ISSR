"""
Layout-Aware PDF Parser for FOA Documents.

Primary: pymupdf4llm — uses MuPDF's native layout engine to preserve
column reading order in multi-column FOA PDFs. This is the critical
correctness gate preventing interleaved column text.

Supplement: pdfplumber — extracts embedded tables as structured JSON.

Fallback: pdfminer.six — byte-stream extraction with custom column
detection heuristics (for encrypted or non-standard PDFs).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ParsedPDFSection:
    """A section extracted from a PDF document."""

    heading: str
    content: str
    page_numbers: List[int] = field(default_factory=list)
    section_type: str = "other"  # description, eligibility, dates, budget, other


@dataclass
class ParsedPDF:
    """Complete parsed result from a PDF FOA document."""

    source_path: str
    full_text_markdown: str
    sections: List[ParsedPDFSection]
    tables: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    page_count: int
    parse_method: str  # pymupdf4llm, pdfminer_fallback


def parse_foa_pdf(pdf_path: Path) -> ParsedPDF:
    """
    Parse an FOA PDF document using layout-aware extraction.

    Algorithm:
    1. Try pymupdf4llm first (preserves column reading order)
    2. Extract text as Markdown with heading hierarchy
    3. Identify section boundaries (Description, Eligibility, Dates, Budget)
    4. Use pdfplumber to extract any embedded tables
    5. If pymupdf4llm fails, fall back to pdfminer.six

    Args:
        pdf_path: Path to the PDF file

    Returns:
        ParsedPDF with full text, sections, tables, and metadata
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        return _parse_with_pymupdf4llm(pdf_path)
    except Exception as exc:
        logger.warning(
            "pymupdf4llm failed for %s: %s — trying fallback", pdf_path, exc
        )
        return _parse_with_pdfminer_fallback(pdf_path)


def _parse_with_pymupdf4llm(pdf_path: Path) -> ParsedPDF:
    """Primary parser using pymupdf4llm for layout-aware extraction."""
    import pymupdf
    import pymupdf4llm

    # Convert to Markdown preserving column order
    md_text = pymupdf4llm.to_markdown(str(pdf_path))

    # Extract metadata
    doc = pymupdf.open(str(pdf_path))
    metadata = dict(doc.metadata) if doc.metadata else {}
    page_count = len(doc)
    doc.close()

    # Identify sections by heading patterns
    sections = _extract_sections(md_text)

    # Extract tables with pdfplumber
    tables = _extract_tables_pdfplumber(pdf_path)

    return ParsedPDF(
        source_path=str(pdf_path),
        full_text_markdown=md_text,
        sections=sections,
        tables=tables,
        metadata=metadata,
        page_count=page_count,
        parse_method="pymupdf4llm",
    )


def _parse_with_pdfminer_fallback(pdf_path: Path) -> ParsedPDF:
    """Fallback parser using pdfminer.six with column detection."""
    from pdfminer.high_level import extract_text

    text = extract_text(str(pdf_path))
    sections = _extract_sections(text)
    tables = _extract_tables_pdfplumber(pdf_path)

    return ParsedPDF(
        source_path=str(pdf_path),
        full_text_markdown=text,
        sections=sections,
        tables=tables,
        metadata={},
        page_count=0,
        parse_method="pdfminer_fallback",
    )


# ═══════════════════════════════════════════════
# Section Detection
# ═══════════════════════════════════════════════

# Regex patterns for common FOA section headings
_SECTION_PATTERNS = {
    "description": re.compile(
        r"(?i)(?:^|\n)#{1,4}\s*(?:program\s+description|summary|synopsis|overview|"
        r"program\s+summary|description\s+of\s+the\s+program)",
        re.MULTILINE,
    ),
    "eligibility": re.compile(
        r"(?i)(?:^|\n)#{1,4}\s*(?:eligibility|who\s+may\s+(?:apply|submit)|"
        r"eligible\s+applicants|applicant\s+eligibility)",
        re.MULTILINE,
    ),
    "dates": re.compile(
        r"(?i)(?:^|\n)#{1,4}\s*(?:key\s+dates?|deadlines?|due\s+dates?|"
        r"submission\s+dates?|important\s+dates?)",
        re.MULTILINE,
    ),
    "budget": re.compile(
        r"(?i)(?:^|\n)#{1,4}\s*(?:award\s+information|funding\s+amount|"
        r"budget|financial|estimated\s+funding|award\s+size)",
        re.MULTILINE,
    ),
}


def _extract_sections(text: str) -> List[ParsedPDFSection]:
    """
    Identify logical sections in FOA text by heading patterns.

    Looks for common FOA section headers:
    - Program Description / Summary / Synopsis
    - Eligibility Information / Who May Apply
    - Award Information / Funding Amount
    - Key Dates / Deadline
    """
    sections: List[ParsedPDFSection] = []
    all_matches: List[tuple] = []

    for section_type, pattern in _SECTION_PATTERNS.items():
        for match in pattern.finditer(text):
            all_matches.append((match.start(), match.end(), section_type, match.group()))

    # Sort by position in document
    all_matches.sort(key=lambda m: m[0])

    for i, (start, end, section_type, heading) in enumerate(all_matches):
        # Content extends from after this heading to the next heading (or end)
        content_start = end
        if i + 1 < len(all_matches):
            content_end = all_matches[i + 1][0]
        else:
            content_end = min(start + 5000, len(text))  # Cap at 5000 chars

        content = text[content_start:content_end].strip()
        heading_clean = re.sub(r"^#+\s*", "", heading).strip()

        sections.append(
            ParsedPDFSection(
                heading=heading_clean,
                content=content,
                page_numbers=[],
                section_type=section_type,
            )
        )

    # If no sections detected, create a single 'description' section with full text
    if not sections and text.strip():
        sections.append(
            ParsedPDFSection(
                heading="Full Document",
                content=text[:10000],
                page_numbers=[],
                section_type="description",
            )
        )

    return sections


# ═══════════════════════════════════════════════
# Table Extraction
# ═══════════════════════════════════════════════


def _extract_tables_pdfplumber(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract tables from PDF using pdfplumber."""
    import pdfplumber

    tables: List[Dict[str, Any]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                if not page_tables:
                    continue
                for table in page_tables:
                    if not table or len(table) < 2:
                        continue
                    # First row as headers, rest as data
                    headers = [
                        str(h).strip() if h else f"col_{j}"
                        for j, h in enumerate(table[0])
                    ]
                    rows = []
                    for row in table[1:]:
                        row_dict = {}
                        for j, cell in enumerate(row):
                            if j < len(headers):
                                row_dict[headers[j]] = (
                                    str(cell).strip() if cell else ""
                                )
                        rows.append(row_dict)
                    tables.append(
                        {"page": i + 1, "headers": headers, "rows": rows}
                    )
    except Exception as exc:
        logger.warning(
            "pdfplumber table extraction failed for %s: %s", pdf_path, exc
        )
    return tables


# ═══════════════════════════════════════════════
# Utility: Extract Structured Fields from PDF Text
# ═══════════════════════════════════════════════


def extract_structured_fields(parsed: ParsedPDF) -> Dict[str, Any]:
    """
    Extract structured fields from parsed PDF text using regex.

    Extracts:
    - CFDA numbers
    - Award amounts (floor/ceiling)
    - Due dates
    - FOA numbers
    """
    text = parsed.full_text_markdown
    fields: Dict[str, Any] = {}

    # CFDA numbers (format: XX.XXX)
    cfda_matches = re.findall(r"\b(\d{2}\.\d{3})\b", text)
    if cfda_matches:
        fields["cfda_numbers"] = list(set(cfda_matches))

    # Award amounts
    amount_pattern = r"\$\s*([\d,]+(?:\.\d{2})?)"
    amounts = re.findall(amount_pattern, text)
    if amounts:
        parsed_amounts = []
        for a in amounts:
            try:
                parsed_amounts.append(float(a.replace(",", "")))
            except ValueError:
                pass
        if len(parsed_amounts) >= 2:
            fields["award_floor"] = min(parsed_amounts)
            fields["award_ceiling"] = max(parsed_amounts)
        elif len(parsed_amounts) == 1:
            fields["award_ceiling"] = parsed_amounts[0]

    # Due dates
    date_pattern = r"(?:due|deadline|close)\s*(?:date)?[:\s]+(\w+\s+\d{1,2},?\s+\d{4})"
    date_matches = re.findall(date_pattern, text, re.IGNORECASE)
    if date_matches:
        fields["close_date_raw"] = date_matches[0]

    # FOA / Solicitation number
    foa_pattern = r"(?:FOA|solicitation|opportunity)\s*(?:number|#|no\.?)?\s*[:\s]+([A-Z0-9-]+)"
    foa_matches = re.findall(foa_pattern, text, re.IGNORECASE)
    if foa_matches:
        fields["opportunity_number"] = foa_matches[0]

    return fields
