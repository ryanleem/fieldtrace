from sqlalchemy import and_, select

from app.models import Document, DocumentChunk, DocumentPage
from app.schemas.search import Evidence


def filtered_statement(request, score):
    statement = select(DocumentChunk, Document, DocumentPage.printed_page_label, score.label("score")).join(
        Document, DocumentChunk.document_id == Document.id).join(
        DocumentPage, and_(DocumentPage.document_id == DocumentChunk.document_id,
                           DocumentPage.page_number == DocumentChunk.page_number))
    for field in ("equipment_model", "equipment_family", "document_id"):
        value = getattr(request, field)
        if value is not None:
            column = Document.id if field == "document_id" else getattr(Document, field)
            statement = statement.where(column == value)
    return statement


def to_evidence(row, rank, mode):
    chunk, document, label, score = row
    return Evidence(
        rank=rank, chunk_id=chunk.id, document_id=document.id, document_title=document.title,
        source_url=document.source_url,
        citation_url=f"{document.source_url.split('#')[0]}#page={chunk.page_number}" if document.source_url else None,
        document_number=document.document_number, revision=document.revision,
        equipment_model=document.equipment_model, equipment_family=document.equipment_family,
        page_number=chunk.page_number, printed_page_label=label, section_title=chunk.section_title,
        content_type=chunk.content_type, chunk_index=chunk.chunk_index, chunk_text=chunk.chunk_text,
        source_blocks=chunk.source_blocks, safety_context=chunk.safety_context,
        extraction_notes=chunk.extraction_notes,
        **{f"{mode}_rank": rank, f"{mode}_score": float(score)},
    )
