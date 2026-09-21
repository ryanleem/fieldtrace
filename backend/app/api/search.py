from fastapi import APIRouter, HTTPException

from app.db.session import get_engine
from app.schemas.search import SearchRequest, SearchResponse
from app.services.embeddings import get_embedder
from app.services.hybrid_search import search_all

router = APIRouter(tags=["evidence"])


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    try:
        results = search_all(get_engine(), request, get_embedder())
        return SearchResponse(query=request.query, results=results["hybrid"])
    except ValueError as error:
        raise HTTPException(422, detail={"errors": [str(error)]})
