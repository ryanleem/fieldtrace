from fastapi import APIRouter, HTTPException

from app.db.session import get_engine
from app.schemas.document import IngestRequest, IngestResult
from app.services.embeddings import get_embedder
from app.services.ingestion import ingest

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=IngestResult)
def ingest_document(request: IngestRequest):
    try:
        return ingest(get_engine(), request, get_embedder())
    except FileNotFoundError:
        raise HTTPException(404, detail={"errors": ["Local PDF not found in data/manuals"]})
    except ValueError as error:
        raise HTTPException(422, detail={"errors": [str(error)]})
