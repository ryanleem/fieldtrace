from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.init_db import assert_compatible
from app.models import Document, DocumentChunk, DocumentPage
from app.schemas.document import IngestRequest, IngestResult
from app.services.chunking import chunk_pages
from app.services.pdf_parser import parse_pdf


def embedding_text(chunk, embedder):
    # Metadata aids retrieval, but the displayed evidence remains source text only.
    prefix = chunk.section_title or ""
    if embedder.token_count(prefix) > 35:
        prefix = ""  # Do not let an unusually long heading silently truncate evidence.
    return f"{prefix}\n{chunk.chunk_text}".strip()


def ingest(engine, request: IngestRequest, embedder, settings=None, *, replace=False):
    settings = settings or get_settings()
    root = settings.manuals_dir.resolve()
    path = (root / request.filename).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".pdf":
        raise ValueError("PDF must be inside configured data/manuals directory")
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-"):
        raise ValueError("File is not a PDF")
    digest = hashlib.sha256(raw).hexdigest()
    if request.verified_sha256 and request.verified_sha256 != digest:
        raise ValueError("PDF hash differs from metadata-verified manifest; reverify before ingestion")
    document_id = uuid5(NAMESPACE_URL, f"abb-guardian:sha256:{digest}")
    with Session(engine) as session, session.begin():
        assert_compatible(session, embedder, settings)
        # Serializes identical PDF ingestion, including concurrent API requests.
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": int(digest[:15], 16)})
        existing = session.scalar(select(Document).where(Document.sha256 == digest))
        if existing and not replace:
            return IngestResult(document_id=existing.id, pages_processed=existing.pages_processed,
                                chunks_created=existing.chunks_created, duplicate=True, warnings=existing.warnings)
        if existing:
            session.delete(existing)
            session.flush()
        pages = parse_pdf(path, document_id)
        budget = embedder.max_tokens - 48
        if budget < 32:
            raise ValueError("Selected embedding model has insufficient context for technical chunks")
        chunks = chunk_pages(pages, embedder.token_count, max_tokens=budget)
        if not chunks:
            raise ValueError("PDF has no extractable text; OCR is not implemented in Step 1")
        warnings = [{"page_number": page.page_number, "messages": page.warnings}
                    for page in pages if page.warnings]
        metadata = request.model_dump(exclude={"filename", "verified_sha256"})
        document = Document(id=document_id, **metadata, local_path=str(path), sha256=digest,
                            pages_processed=len(pages), chunks_created=len(chunks), warnings=warnings)
        session.add(document)
        session.flush()
        session.add_all([DocumentPage(document_id=document_id, page_number=page.page_number,
                                      printed_page_label=page.printed_page_label,
                                      extracted_text=page.text, extraction_method=page.extraction_method,
                                      warnings=page.warnings) for page in pages])
        session.flush()
        size = settings.embedding_batch_size
        for start in range(0, len(chunks), size):
            batch = chunks[start:start+size]
            vectors = embedder.encode([embedding_text(chunk, embedder) for chunk in batch])
            for chunk, vector in zip(batch, vectors, strict=True):
                search_text = "\n".join(filter(None, [request.title, request.equipment_model,
                                                      request.equipment_family, chunk.section_title, chunk.chunk_text]))
                session.add(DocumentChunk(**asdict(chunk), embedding=vector, search_text=search_text))
            session.flush()
        # A single database transaction: no half-ingested documents on failures.
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    report = IngestResult(document_id=document_id, pages_processed=len(pages),
                          chunks_created=len(chunks), warnings=warnings)
    try:
        (settings.processed_dir / f"{document_id}.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8")
    except OSError as error:
        report.warnings.append({"messages": [f"Database committed, but local report could not be saved: {error}"]})
    return report
