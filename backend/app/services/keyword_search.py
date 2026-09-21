import re

from sqlalchemy import func, literal_column, or_

from app.models import DocumentChunk
from app.services.search_common import filtered_statement, to_evidence


def keyword_search(session, request, top_n):
    # OR across natural-language lexemes avoids requiring conversational filler words.
    # Technical-only queries keep their identifiers together with AND.
    tokens = re.findall(r"[\w]+(?:[-./][\w]+)*", request.query, flags=re.UNICODE)
    if not tokens:
        return []
    technical = [token for token in tokens if any(c.isdigit() for c in token)]
    simple = literal_column("'simple'::regconfig")
    english = literal_column("'english'::regconfig")
    prose_query = " OR ".join(tokens)
    stem_query = func.websearch_to_tsquery(english, prose_query)
    simple_query = func.plainto_tsquery(simple, " ".join(technical)) if technical else None
    combined = stem_query.op("||")(simple_query) if technical else stem_query
    match = DocumentChunk.search_vector.op("@@")(combined)
    if technical:
        # Prevent an exact fault/terminal identifier being drowned out by broad prose matches.
        match = DocumentChunk.search_vector.op("@@")(simple_query)
    score = func.ts_rank_cd(DocumentChunk.search_vector, combined, 32)
    statement = filtered_statement(request, score).where(match).order_by(score.desc(), DocumentChunk.id).limit(top_n)
    return [to_evidence(row, rank, "keyword") for rank, row in enumerate(session.execute(statement), 1)]
