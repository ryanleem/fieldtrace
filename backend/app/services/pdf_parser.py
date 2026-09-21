"""Page-local extraction with conservative headings and bordered table rows.

Coordinates are PDF points, top-left origin. No OCR or image interpretation.
Unstructured page text is retained separately even when structured extraction works.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
from uuid import UUID

import pymupdf


@dataclass
class Unit:
    text: str
    block_id: str
    bbox: list[float] | None = None
    section_title: str | None = None
    content_type: str = "paragraph"
    heading: bool = False


@dataclass
class Page:
    document_id: UUID
    page_number: int
    text: str
    units: list[Unit] = field(default_factory=list)
    printed_page_label: str | None = None
    extraction_method: str = "pymupdf"
    warnings: list[str] = field(default_factory=list)


def clean(text):
    # Preserve line structure and technical symbols, remove invalid null characters.
    return text.replace("\x00", "").replace("\u00ad", "").strip()


def norm(text):
    return re.sub(r"\s+", " ", text).strip().casefold().lstrip("■ ")


def parse_pdf(path: Path, document_id: UUID):
    pages = []
    with pymupdf.open(path) as pdf:
        if pdf.needs_pass:
            raise ValueError("Encrypted PDF requires decryption before ingestion")
        toc = pdf.get_toc()
        headings = {norm(title) for _, title, _ in toc}
        # Only carry chapter-level context between pages; deep headings must be detected locally.
        chapters = sorted([(page, title) for level, title, page in toc if level == 1])
        for index, source in enumerate(pdf):
            result = Page(document_id=document_id, page_number=index + 1, text="")
            try:
                result.text = clean(source.get_text("text", sort=True))
                result.printed_page_label = source.get_label() or None
                if not result.text:
                    result.warnings.append("No extractable text: blank, image-only, or scanned page; OCR not implemented.")
                chapter = next((title for start, title in reversed(chapters) if start <= index + 1), None)
                table_boxes = []
                positioned = []
                try:
                    tables = source.find_tables(strategy="lines_strict").tables
                    for table_index, table in enumerate(tables):
                        rows = table.extract()
                        if len(rows) < 2 or len(rows[0]) < 2:
                            continue
                        table_boxes.append(pymupdf.Rect(table.bbox))
                        header = [clean(cell or "").replace("\n", " ") for cell in rows[0]]
                        header_text = " | ".join(header)
                        for row_index, row in enumerate(rows[1:], start=1):
                            if not any(row):
                                continue
                            # Explicit separators retain empty cells; never infer missing cell values.
                            row_text = " | ".join(clean(cell or "") for cell in row)
                            text = f"Table columns: {header_text}\n{row_text}"
                            bbox = list(table.rows[row_index].bbox)
                            kind = "fault_code" if re.match(r"^[A-F0-9]{4}\b", row_text) else "table"
                            positioned.append((bbox[1], bbox[0], Unit(text, f"p{index+1}-t{table_index}-r{row_index}", bbox, content_type=kind)))
                        result.warnings.append(f"Table {table_index}: cell text extracted; merged/empty cells left as extracted; visually verify row relationships.")
                except Exception as error:
                    table_boxes = []
                    positioned = []
                    result.warnings.append(f"Table extraction failed; page-text fallback: {type(error).__name__}: {error}")
                for block_index, block in enumerate(source.get_text("dict", sort=True)["blocks"]):
                    if block.get("type") != 0:
                        continue
                    lines = []
                    for line in block["lines"]:
                        kept_spans = []
                        for span in line["spans"]:
                            box = pymupdf.Rect(span["bbox"])
                            center = (box.tl + box.br) / 2
                            if not any(center in table_box for table_box in table_boxes):
                                kept_spans.append(span["text"])
                        content = clean("".join(kept_spans))
                        if content:
                            lines.append(content)
                    if not lines:
                        continue
                    text = "\n".join(lines)
                    box = list(block["bbox"])
                    sizes = [s["size"] for line in block["lines"] for s in line["spans"]]
                    if text.isdigit() and max(sizes, default=0) > 30:
                        continue  # Decorative chapter number; kept in raw page text.
                    # Page running headers/footers are retained in page text, not indexed as content.
                    if (box[1] < 55 or box[3] > source.rect.height - 25) and len(text) < 160:
                        continue
                    is_heading = norm(text) in headings
                    if not is_heading and len(text) < 140:
                        is_heading = bool(re.match(r"^\d+\.\d+(?:\.\d+)*\s+[A-Za-z]", text))
                    kind = "paragraph"
                    if re.match(r"^(WARNING|CAUTION|NOTE)\b", text, re.I):
                        kind = "warning"
                    elif re.match(r"^\d+[.)]\s", text) and not is_heading:
                        kind = "procedure"
                    elif re.match(r"^(Figure|Fig\.)\s+\d+", text):
                        kind = "diagram"  # Caption only; image content is not interpreted.
                    positioned.append((box[1], box[0], Unit(text, f"p{index+1}-b{block_index}", box, content_type=kind, heading=is_heading)))
                current_section = chapter
                for _, _, unit in sorted(positioned, key=lambda item: (item[0], item[1])):
                    if unit.heading:
                        current_section = re.sub(r"\s+", " ", unit.text)
                    unit.section_title = current_section
                    result.units.append(unit)
                merged = []
                for unit in result.units:
                    if merged and re.fullmatch(r"(?:WARNING|CAUTION|NOTE)[:!.]?", merged[-1].text, re.I) and not unit.heading:
                        previous = merged[-1]
                        previous.text += "\n" + unit.text
                        previous.content_type = "warning"
                        previous.block_id += "+" + unit.block_id
                        if previous.bbox and unit.bbox:
                            previous.bbox = list(pymupdf.Rect(previous.bbox) | pymupdf.Rect(unit.bbox))
                    else:
                        merged.append(unit)
                result.units = merged
                if result.text and not result.units:
                    result.units = [Unit(result.text, f"p{index+1}-fallback", section_title=chapter)]
                    result.warnings.append("No structured content found; retained full page text.")
                if source.get_images():
                    result.warnings.append("Embedded images present; only surrounding text/captions extracted, no image interpretation.")
            except Exception as error:
                from pypdf import PdfReader
                try:
                    result.text = clean(PdfReader(path).pages[index].extract_text() or "")
                    result.units = [Unit(result.text, f"p{index+1}-fallback")] if result.text else []
                    result.extraction_method = "pypdf_fallback"
                    result.warnings.append(f"PyMuPDF failed; pypdf fallback used: {type(error).__name__}: {error}")
                except Exception as fallback_error:
                    raise ValueError(f"Both parsers failed on physical PDF page {index+1}") from fallback_error
            pages.append(result)
    return pages
