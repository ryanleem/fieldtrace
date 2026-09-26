"""Check whether the current retrieval filters have any indexed evidence."""
from sqlalchemy import literal, select

from app.models import DocumentChunk
from app.schemas.search import SearchRequest
from app.services.search_common import filtered_statement


def indexed_manual_coverage(db, filters):
    # Reuse retrieval's exact model/family filters and document/page joins. A
    # manifest entry or stale Document.chunks_created counter is not evidence.
    request = SearchRequest(query='manual coverage', **filters)
    query = filtered_statement(request, literal(0)).with_only_columns(DocumentChunk.id)
    return bool(db.scalar(select(query.exists())))
