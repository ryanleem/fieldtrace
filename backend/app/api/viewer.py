"""Read-only Step 5 views; never expose provider prompts or candidate audits."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db.session import get_engine
from app.models.troubleshooting import TroubleshootingRun
from app.services.inspection_images import load_image, image_path
from app.services.equipment_sessions import load_session
from app.api.equipment import call

from app.auth import session_access

router = APIRouter(dependencies=[Depends(session_access)], prefix='/sessions', tags=['source viewer'])


def cited_source(engine, session_id, run_id, chunk_id):
    with Session(engine) as db:
        load_session(db, session_id)
        run = db.get(TroubleshootingRun, run_id)
        if not run or run.session_id != session_id:
            raise HTTPException(404, 'Source not found in this session')
        citation = next((s for s in run.final.get('sources', []) if s['chunk_id'] == str(chunk_id)), None)
        if citation:
            for attempt in reversed(run.audit.get('attempts', [])):
                chunk = next((e for e in attempt.get('evidence', []) if e['chunk_id'] == str(chunk_id)), None)
                if chunk:
                    return dict(citation, chunk_text=chunk['chunk_text'])
        raise HTTPException(404, 'This chunk is not a final citation in this run')


@router.get('/{session_id}/troubleshooting/runs/{run_id}/sources/{chunk_id}')
def source(session_id: UUID, run_id: UUID, chunk_id: UUID):
    return call(cited_source, get_engine(), session_id, run_id, chunk_id)


@router.get('/{session_id}/images/{image_id}/file')
def photo(session_id: UUID, image_id: UUID):
    def read():
        with Session(get_engine()) as db:
            load_session(db, session_id)
            record = load_image(db, session_id, image_id)
            path = image_path(get_settings(), record)
            if not path.is_file(): raise HTTPException(404, 'Image file is unavailable')
            return FileResponse(path, media_type=record.mime_type,
                                headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})
    return call(read)
