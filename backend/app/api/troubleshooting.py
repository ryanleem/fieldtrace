from uuid import UUID
from fastapi import APIRouter, Depends
from app.api.equipment import call
from app.config import get_settings
from app.db.session import get_engine
from app.services.embeddings import get_embedder
from app.services.troubleshooting_provider import get_troubleshooting_provider
from app.services import troubleshooting_sessions as service
from app.schemas.troubleshooting import TroubleshootingInput, SymptomInput

router = APIRouter(prefix='/sessions/{session_id}/troubleshooting', tags=['grounded troubleshooting'])


@router.put('')
def update(session_id: UUID, payload: TroubleshootingInput):
    return call(service.update, get_engine(), session_id, payload)


@router.get('')
def state(session_id: UUID):
    return call(service.get_state, get_engine(), session_id)


@router.post('/symptoms')
def symptom(session_id: UUID, payload: SymptomInput):
    return call(service.update, get_engine(), session_id, TroubleshootingInput(reported_symptoms=[payload.symptom]))


@router.post('/run')
def run(session_id: UUID, provider=Depends(get_troubleshooting_provider), embedder=Depends(get_embedder)):
    return call(service.run, get_engine(), session_id, provider, embedder, get_settings())


@router.post('/follow-up')
def follow_up(session_id: UUID, payload: TroubleshootingInput,
              provider=Depends(get_troubleshooting_provider), embedder=Depends(get_embedder)):
    call(service.update, get_engine(), session_id, payload)
    return call(service.run, get_engine(), session_id, provider, embedder, get_settings())


@router.get('/runs/{run_id}')
def history(session_id: UUID, run_id: UUID, include_evidence: bool = False):
    return call(service.get_run, get_engine(), session_id, run_id, include_evidence)
