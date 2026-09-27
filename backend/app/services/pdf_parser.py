"""Page-local extraction with conservative headings and bordered table rows.

Coordinates are unrotated crop-local PDF points, top-left origin. Optional local OCR for textless pages.
No diagram interpretation; OCR output is unverified transcription.
Unstructured page text is retained separately even when structured extraction works.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
from uuid import UUID

import pymupdf


class DocumentOCRError(RuntimeError):
    """OCR failed; do not silently replace its output with empty fallback text."""


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


def extract_scanned_page(source, result, provider):
    """Bounded RGB raster; match native extraction's unrotated PDF coordinates."""
    from PIL import Image
    rect = source.rect
    scale = min(2.0, 2400 / max(rect.width, rect.height))
    pix = source.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    ocr = provider.extract(image)
    result.text = clean(ocr.raw_text)
    result.extraction_method = "ocr:" + ocr.provider
    result.warnings = ["OCR transcription: verify technical identifiers and table relationships against the original page."]
    result.warnings.extend(ocr.warnings)
    for i, line in enumerate(ocr.lines):
        text = clean(line.get("text", ""))
        if not text:
            continue
        points = line.get("bbox") or []
        box = None
        if points:
            xs, ys = zip(*points)
            box = [max(0, min(xs) * rect.width / pix.width), max(0, min(ys) * rect.height / pix.height),
                   min(rect.width, max(xs) * rect.width / pix.width), min(rect.height, max(ys) * rect.height / pix.height)]
        if box is not None:
            box = list(pymupdf.Rect(box) * source.derotation_matrix)
        result.units.append(Unit(text, f"p{result.page_number}-ocr-{i}", box, content_type="ocr_text"))
    if not result.units and result.text:
        result.units = [Unit(result.text, f"p{result.page_number}-ocr", content_type="ocr_text")]


def parse_pdf(path: Path, document_id: UUID, *, ocr_enabled=False, ocr_provider=None):
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
                    if ocr_enabled:
                        try:
                            if ocr_provider is None:
                                from app.services.equipment_ocr import get_ocr_provider
                                ocr_provider = get_ocr_provider()
                            extract_scanned_page(source, result, ocr_provider)
                        except Exception as error:
                            raise DocumentOCRError("Document OCR failed on page " + str(index + 1)) from error
                        if not result.text:
                            result.warnings.append("OCR found no text; page may be blank or contain only graphics.")
                        pages.append(result)
                        continue
                    result.warnings.append("No extractable text; enable DOCUMENT_OCR_ENABLED for textless scanned pages.")
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
            except DocumentOCRError:
                raise
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
