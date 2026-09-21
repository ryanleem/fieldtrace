from uuid import uuid4

import pytest

from app.services.chunking import chunk_pages, split_oversized
from app.services.pdf_parser import Page, Unit


def test_pages_documents_and_metadata_survive():
    doc = uuid4()
    pages = [Page(doc, 7, "alpha", [Unit("alpha beta", "b1", [1, 2, 3, 4], "Section A")]),
             Page(doc, 8, "gamma", [Unit("gamma delta", "b2", None, "Section A")])]
    chunks = chunk_pages(pages)
    assert [c.document_id for c in chunks] == [doc, doc]
    assert [c.page_number for c in chunks] == [7, 8]
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert chunks[0].section_title == "Section A"
    assert chunks[0].source_blocks == [{"block_id": "b1", "bbox": [1, 2, 3, 4]}]


def test_oversized_content_is_complete_and_bounded():
    content = " ".join(f"token{i}" for i in range(120))
    doc = uuid4()
    chunks = chunk_pages([Page(doc, 3, content, [Unit(content, "large", section_title="Section")])], max_tokens=20)
    assert len(chunks) == 6
    assert " ".join(c.chunk_text for c in chunks) == content
    assert all(c.document_id == doc and c.page_number == 3 and c.extraction_notes for c in chunks)


def test_empty_page_and_unrelated_headings():
    doc = uuid4()
    assert chunk_pages([Page(doc, 1, "")]) == []
    chunks = chunk_pages([Page(doc, 2, "a b", [Unit("A", "a", section_title="A", heading=True),
                                               Unit("Body A", "a-body", section_title="A"),
                                               Unit("B", "b", section_title="B", heading=True),
                                               Unit("Body B", "b-body", section_title="B")])])
    assert len(chunks) == 2
    assert chunks[0].section_title == "A" and chunks[1].section_title == "B"


def test_headings_are_attached_to_evidence_not_standalone_hits():
    doc = uuid4()
    chunks = chunk_pages([Page(doc, 1, "", [Unit("Parent", "p", section_title="Parent", heading=True),
                                           Unit("Child", "c", section_title="Child", heading=True),
                                           Unit("Evidence body.", "body", section_title="Child")])])
    assert len(chunks) == 1 and "Parent" in chunks[0].chunk_text and "Evidence body" in chunks[0].chunk_text


def test_fault_fragments_retain_code_and_table_header():
    doc = uuid4()
    content = "Table columns: Code | Description\nA4F6 | " + "placeholder " * 200
    chunks = chunk_pages([Page(doc, 1, content, [Unit(content, "row", content_type="fault_code")])], max_tokens=70)
    assert len(chunks) > 1
    assert all("A4F6" in c.chunk_text and "Table columns" in c.chunk_text for c in chunks)
    assert all(len(c.chunk_text.split()) <= 70 for c in chunks)


def test_warning_remains_linked_after_split():
    doc = uuid4()
    warning = "WARNING: synthetic test fixture, not maintenance guidance."
    chunks = chunk_pages([Page(doc, 2, "", [Unit(warning, "warning", section_title="S", content_type="warning"),
                                            Unit(" ".join(["placeholder"]*50), "procedure", section_title="S", content_type="procedure")])], max_tokens=15)
    assert len(chunks) > 1
    assert all(c.safety_context[0]["text"] == warning for c in chunks)
    assert all(c.safety_context[0]["document_id"] == str(doc) for c in chunks)


def test_missing_identity_rejected():
    with pytest.raises(ValueError):
        chunk_pages([Page(None, 1, "")])


def test_malformed_long_token_is_not_dropped():
    text = "x" * 90
    chunks = split_oversized(text, len, 20)
    assert "".join(chunks) == text
    assert max(map(len, chunks)) <= 20
