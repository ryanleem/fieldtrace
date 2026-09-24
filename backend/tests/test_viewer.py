from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.api import viewer
from app.models.troubleshooting import TroubleshootingRun
from app.models.vision import SessionImage
from app.services import troubleshooting_sessions as service
from app.schemas.troubleshooting import TroubleshootingInput
from test_troubleshooting import troubleshooting_db, MockLLM, evidence
from test_vision import inspection_db, upload


@pytest.mark.integration
def test_source_view_returns_only_cited_text_and_provenance(troubleshooting_db):
    engine,settings,sid,embedder=troubleshooting_db
    rows=[evidence()]
    service.update(engine,sid,TroubleshootingInput(reported_symptoms=['Fault 5091']))
    state=service.run(engine,sid,MockLLM(),embedder,settings,lambda p:rows)
    rid=UUID(state['retrieved_evidence_history'][-1]['run_id'])
    result=viewer.cited_source(engine,sid,rid,rows[0].chunk_id)
    assert result['chunk_text']==rows[0].chunk_text and result['page_number']==12
    assert not {'audit','calls','candidate','raw','input'}&set(result)
    with pytest.raises(HTTPException):viewer.cited_source(engine,sid,rid,uuid4())
    from app.services.equipment_sessions import create_session
    other=create_session(engine).session_id
    with pytest.raises(HTTPException):viewer.cited_source(engine,other,rid,rows[0].chunk_id)
    with Session(engine) as db,db.begin():
        row=db.get(TroubleshootingRun,rid);row.final={**row.final,'sources':[]}
    with pytest.raises(HTTPException):viewer.cited_source(engine,sid,rid,rows[0].chunk_id)


@pytest.mark.integration
def test_image_view_enforces_session_and_safe_stored_path(inspection_db,monkeypatch):
    engine,settings,sid,_=inspection_db
    image=upload(engine,settings,sid,view_label='front')
    app=FastAPI();app.include_router(viewer.router)
    from conftest import authenticated_client
    authenticated_client(app, monkeypatch, engine, sid)
    monkeypatch.setattr(viewer,'get_engine',lambda:engine);monkeypatch.setattr(viewer,'get_settings',lambda:settings)
    client=TestClient(app);path=f'/sessions/{sid}/images/{image["id"]}/file'
    response=client.get(path)
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    assert response.headers['x-content-type-options']=='nosniff'
    assert client.get(f'/sessions/{uuid4()}/images/{image["id"]}/file').status_code==404
    with Session(engine) as db,db.begin():db.get(SessionImage,image['id']).stored_path='../.env'
    assert client.get(path).status_code==422
