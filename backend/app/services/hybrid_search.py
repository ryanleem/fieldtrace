from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.init_db import assert_compatible
from app.services.keyword_search import keyword_search
from app.services.semantic_search import semantic_search
from app.services.query_normalization import retrieval_query


def reciprocal_rank_fusion(semantic, keyword, k=60, top_k=10):
    if k < 1:
        raise ValueError("RRF k must be positive")
    merged = {}
    for mode, results in (("semantic", semantic), ("keyword", keyword)):
        seen = set()
        for rank, result in enumerate(results, 1):
            if result.chunk_id in seen:
                continue
            seen.add(result.chunk_id)
            if result.chunk_id not in merged:
                merged[result.chunk_id] = result.model_copy(update={
                    "rrf_score": 0.0, "semantic_rank": None, "semantic_score": None,
                    "keyword_rank": None, "keyword_score": None,
                })
            item = merged[result.chunk_id]
            item.rrf_score += 1 / (k + rank)
            setattr(item, f"{mode}_rank", rank)
            setattr(item, f"{mode}_score", getattr(result, f"{mode}_score"))
    ranked = sorted(merged.values(), key=lambda x: (-x.rrf_score, str(x.chunk_id)))[:top_k]
    return [result.model_copy(update={"rank": i}) for i, result in enumerate(ranked, 1)]


def search_all(engine, request, embedder, settings=None):
    settings = settings or get_settings()
    normalized = request.model_copy(update={"query": retrieval_query(request)})
    vector = embedder.encode([normalized.query], query=True)[0]
    with Session(engine) as session:
        assert_compatible(session, embedder, settings)
        semantic = semantic_search(session, normalized, vector, max(settings.semantic_top_n, request.top_k))
        keyword = keyword_search(session, normalized, max(settings.keyword_top_n, request.top_k))
    hybrid = reciprocal_rank_fusion(semantic, keyword, settings.rrf_k, request.top_k)
    return {"semantic": semantic, "keyword": keyword, "hybrid": hybrid}
