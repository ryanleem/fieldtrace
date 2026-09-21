from sqlalchemy import text

from app.models import DocumentChunk
from app.services.search_common import filtered_statement, to_evidence


def semantic_search(session, request, query_vector, top_n):
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    statement = filtered_statement(request, 1 - distance)
    # Exact ranking over SQL-filtered rows guarantees small-corpus filter recall.
    # Keep HNSW for future scale, but do not sacrifice filtered recall to ANN post-filtering.
    session.execute(text("SET LOCAL enable_indexscan = off"))
    statement = statement.order_by(distance, DocumentChunk.id).limit(top_n)
    return [to_evidence(row, rank, "semantic") for rank, row in enumerate(session.execute(statement), 1)]
