from uuid import uuid4

import pymupdf
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.init_db import assert_compatible
from app.models import Document, DocumentChunk, DocumentPage
from app.schemas.document import IngestRequest
from app.schemas.search import SearchRequest
from app.services.ingestion import ingest
from app.services.hybrid_search import search_all
from app.services.keyword_search import keyword_search
from app.services.semantic_search import semantic_search


def make_pdf(directory, filename, content):
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 100), content)
        pdf.new_page()  # Empty physical page must still be retained.
        pdf.save(directory / filename)


@pytest.mark.integration
def test_ingestion_idempotency_provenance_and_filters(isolated_db):
    engine, settings, embedder = isolated_db
    requests = []
    for name, model, family, marker in [("one", "ACS880", "Drives", "alpha"), ("two", "OTHER", "Motors", "beta")]:
        make_pdf(settings.manuals_dir, name+".pdf", f"Synthetic retrieval test fixture {marker}: ACS880 F0018 X13 400 V.")
        requests.append(IngestRequest(filename=name+".pdf", title=name, equipment_model=model, equipment_family=family))
    first = ingest(engine, requests[0], embedder, settings)
    duplicate = ingest(engine, requests[0], embedder, settings)
    second = ingest(engine, requests[1], embedder, settings)
    assert duplicate.duplicate and duplicate.document_id == first.document_id
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 2
        assert session.scalar(select(func.count()).select_from(DocumentPage)) == 4
        chunks = session.scalars(select(DocumentChunk)).all()
        assert len(chunks) == first.chunks_created + second.chunks_created
        assert all(c.document_id and c.page_number == 1 and c.chunk_index >= 0 for c in chunks)
        for filters in ({"equipment_family": "Motors"}, {"equipment_model": "OTHER"},
                        {"document_id": second.document_id}):
            request = SearchRequest(query="X13", **filters)
            for result in (semantic_search(session, request, embedder.encode(["X13"])[0], 10),
                           keyword_search(session, request, 10)):
                assert result and {r.document_id for r in result} == {second.document_id}
        absent = SearchRequest(query="X13", equipment_family="missing")
        assert not semantic_search(session, absent, embedder.encode(["X13"])[0], 10)
        assert not keyword_search(session, absent, 10)
        # Technical normalization retains individual identifiers and numeric-unit queries.
        for query in ["F0018", "X13", "400 V", "ACS880"]:
            assert keyword_search(session, SearchRequest(query=query), 10)
        assert not keyword_search(session, SearchRequest(query="F0019"), 10)
        assert not keyword_search(session, SearchRequest(query="!!!"), 10)


@pytest.mark.integration
def test_failed_embeddings_roll_back_and_path_escape_rejected(isolated_db):
    engine, settings, embedder = isolated_db
    make_pdf(settings.manuals_dir, "one.pdf", "Synthetic transaction test fixture.")
    request = IngestRequest(filename="one.pdf", title="Test fixture")
    def fail(*args, **kwargs):
        raise RuntimeError("Injected embedding failure")
    embedder.encode = fail
    with pytest.raises(RuntimeError, match="Injected"):
        ingest(engine, request, embedder, settings)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0
        assert session.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    with pytest.raises(ValueError, match="inside"):
        ingest(engine, request.model_copy(update={"filename": "../escape.pdf"}), embedder, settings)


@pytest.mark.integration
def test_model_space_mismatch_rejected(isolated_db):
    engine, settings, embedder = isolated_db
    with Session(engine) as session:
        with pytest.raises(ValueError, match="mismatch"):
            assert_compatible(session, embedder, settings.model_copy(update={"embedding_model": "different-model"}))


@pytest.mark.corpus
def test_real_abb_relevance_and_provenance():
    from app.db.session import get_engine
    from app.services.embeddings import get_embedder
    engine, embedder = get_engine(), get_embedder()
    motor = search_all(engine, SearchRequest(query="An ABB motor is overheating. What should I inspect?",
                      equipment_family="Induction Motors and Generators", top_k=5), embedder)["hybrid"]
    assert len(motor) == 5
    # Anchored in real source sections, not scores or arbitrary boilerplate.
    assert any(r.page_number in {64, 89, 91, 96, 97, 98, 107}
               and any(term in r.chunk_text.lower() for term in ("temperature", "cooling", "thermal")) for r in motor[:3])
    drive = search_all(engine, SearchRequest(query="ACS880 fault tracing", equipment_model="ACS880", top_k=5), embedder)["hybrid"]
    assert len(drive) == 5 and any(497 <= r.page_number <= 544 and len(r.chunk_text) > 100 for r in drive[:3])
    exact = search_all(engine, SearchRequest(query="A4F6", equipment_model="ACS880", top_k=5), embedder)
    assert exact["keyword"] and any(r.page_number == 503 and "A4F6" in r.chunk_text for r in exact["keyword"])
    with Session(engine) as session:
        assert session.scalar(text("SELECT count(*) FROM document_chunks WHERE document_id IS NULL OR page_number < 1 OR chunk_index IS NULL")) == 0
        assert session.scalar(text("SELECT count(*) FROM documents")) == 2
        assert session.scalar(text("SELECT count(*) FROM document_pages")) == 736
        assert session.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert all(r.citation_url.endswith(f"#page={r.page_number}") for r in motor + drive)
