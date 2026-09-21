from dataclasses import dataclass, field
import re
from uuid import UUID

from app.services.pdf_parser import Page


@dataclass
class Chunk:
    document_id: UUID
    page_number: int
    section_title: str | None
    content_type: str
    chunk_index: int
    chunk_text: str
    source_blocks: list
    safety_context: list = field(default_factory=list)
    extraction_notes: list = field(default_factory=list)


def split_oversized(text, count, budget):
    """Prefer sentence/line boundaries; word splitting is a last-resort size guard."""
    if count(text) <= budget:
        return [text]
    atoms = re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n", text)
    output, current = [], ""
    for atom in atoms:
        if not atom.strip():
            continue
        if count(atom) > budget:
            if current:
                output.append(current)
                current = ""
            words = atom.split()
            for word in words:
                if count(word) > budget:
                    # Rare malformed extracted identifiers: bounded character fallback, explicitly noted upstream.
                    if current:
                        output.append(current)
                        current = ""
                    fragment = ""
                    for char in word:
                        if count(fragment + char) > budget:
                            output.append(fragment)
                            fragment = char
                        else:
                            fragment += char
                    current = fragment
                elif count((current + " " + word).strip()) > budget:
                    output.append(current)
                    current = word
                else:
                    current = (current + " " + word).strip()
        elif count((current + "\n" + atom).strip()) > budget:
            output.append(current)
            current = atom
        else:
            current = (current + "\n" + atom).strip()
    if current:
        output.append(current)
    return output


def chunk_pages(pages: list[Page], token_count=None, max_tokens=200):
    count = token_count or (lambda text: len(text.split()))
    chunks = []
    for page in pages:
        if not page.document_id or page.page_number < 1:
            raise ValueError("Every page requires document identity and a 1-based physical page number")
        pending, refs, section, kind, notes = [], [], None, "paragraph", []
        headings_only = True
        safety = []

        def flush():
            nonlocal pending, refs, notes, headings_only
            if pending and not headings_only:
                chunks.append(Chunk(page.document_id, page.page_number, section, kind, len(chunks),
                                    "\n\n".join(pending), list(refs), list(safety), list(notes)))
            pending, refs, notes = [], [], []
            headings_only = True

        for unit in page.units:
            if not unit.text.strip():
                continue
            if unit.heading or unit.section_title != section:
                if not headings_only:
                    flush()
                section = unit.section_title
                safety = []
            # Never combine unrelated table/fault entries just to fill the token budget.
            if unit.content_type in ("table", "fault_code") or kind in ("table", "fault_code"):
                flush()
            if unit.content_type == "warning":
                flush()
                safety.append({"document_id": str(page.document_id), "page_number": page.page_number,
                               "block_id": unit.block_id, "text": unit.text})
            pieces = split_oversized(unit.text, count, max_tokens)
            if len(pieces) > 1 and unit.content_type in ("table", "fault_code"):
                header, _, row = unit.text.partition("\n")
                identity = row.split("|", 1)[0].strip()
                prefix = header + (f"\nRow identifier: {identity}" if identity else "")
                remaining = max_tokens - count(prefix) - 8
                if remaining >= 32:
                    pieces = [prefix + "\n" + fragment for fragment in split_oversized(row, count, remaining)]
            for piece in pieces:
                if pending and count("\n\n".join(pending + [piece])) > max_tokens:
                    flush()
                if not pending:
                    kind = unit.content_type
                if unit.content_type == "procedure" and kind == "paragraph":
                    kind = "procedure"
                pending.append(piece)
                headings_only = headings_only and unit.heading
                refs.append({"block_id": unit.block_id, "bbox": unit.bbox})
                if len(pieces) > 1:
                    notes.append("Oversized source block split; source block ID links all fragments on this page.")
                if len(pieces) > 1 or unit.content_type in ("table", "fault_code"):
                    flush()
        flush()
    return chunks
