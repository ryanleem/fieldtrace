import time
from types import SimpleNamespace
from uuid import uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import auth
from app.api import equipment, inspection, troubleshooting, viewer
from app.config import Settings
from app.db.init_equipment import initialize_equipment
from app.db.init_vision import initialize_vision
from app.db.init_troubleshooting import initialize_troubleshooting
from app.db.migrate_user_sessions import migrate
from app.models.equipment import EquipmentSession
from app.services import user_sessions
from app.services.equipment_sessions import create_session
from test_equipment import image_bytes


@pytest.fixture
def signed_token(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth, 'signing_keys', lambda url: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    claims = dict(sub=str(uuid4()), iss='https://example.supabase.co/auth/v1',
                  aud='authenticated', role='authenticated', exp=int(time.time())+300, iat=int(time.time()))
    def token(**changes):
        return jwt.encode({**claims, **changes}, key, algorithm='ES256', headers={'kid':'test-key'})
    return token, claims


def test_verified_identity(signed_token):
    token, claims = signed_token
    assert str(auth.verify_token(token(), Settings(_env_file=None, supabase_url='https://example.supabase.co'))) == claims['sub']


@pytest.mark.parametrize('changes', [dict(exp=1), dict(iss='https://attacker.test/auth/v1'),
    dict(aud='other'), dict(role='service_role'), dict(sub='not-a-uuid'), dict(is_anonymous=True), dict(iat=9999999999)])
def test_invalid_claims_are_rejected_without_token_leak(signed_token, changes):
    token, _ = signed_token
    value=token(**changes)
    with pytest.raises(HTTPException) as error:
        auth.verify_token(value, Settings(_env_file=None, supabase_url='https://example.supabase.co'))
    assert error.value.status_code == 401 and value not in error.value.detail


def test_bad_signature_and_malformed_token(signed_token):
    _, claims=signed_token
    bad=jwt.encode(claims,ec.generate_private_key(ec.SECP256R1()),algorithm='ES256')
    for token in [bad,'broken','a'*8193,jwt.encode(claims,'',algorithm='none')]:
        with pytest.raises(HTTPException) as error:
            auth.verify_token(token, Settings(_env_file=None, supabase_url='https://example.supabase.co'))
        assert error.value.status_code==401


def test_missing_and_unavailable_auth_fail_closed(monkeypatch):
    with pytest.raises(HTTPException) as error:
        auth.verify_token('anything',Settings(_env_file=None))
    assert error.value.status_code==503
    def fail(url):raise jwt.PyJWKClientConnectionError('private provider details')
    monkeypatch.setattr(auth,'signing_keys',fail)
    with pytest.raises(HTTPException) as error:
        auth.verify_token('anything',Settings(_env_file=None,supabase_url='https://example.supabase.co'))
    assert error.value.status_code==503 and 'private' not in error.value.detail


@pytest.fixture
def owner_api(isolated_db,monkeypatch):
    engine,settings,_=isolated_db
    initialize_equipment(engine);initialize_vision(engine);initialize_troubleshooting(engine);migrate(engine)
    app=FastAPI()
    for module in (equipment,inspection,troubleshooting,viewer):
        app.include_router(module.router);monkeypatch.setattr(module,'get_engine',lambda:engine)
    monkeypatch.setattr(auth,'get_engine',lambda:engine)
    monkeypatch.setattr(inspection,'get_settings',lambda:settings)
    monkeypatch.setattr(viewer,'get_settings',lambda:settings)
    settings.uploads_dir=settings.processed_dir/'uploads'
    return TestClient(app),app,engine,uuid4(),uuid4()


def as_user(app,user):app.dependency_overrides[auth.require_user]=lambda:user


@pytest.mark.integration
def test_owned_creation_listing_rename_and_legacy_privacy(owner_api):
    c,app,engine,a,b=owner_api
    assert c.post('/sessions',json={'session_name':'Case'}).status_code==401
    assert c.get('/sessions').status_code==401
    legacy=create_session(engine).session_id
    as_user(app,a)
    first=c.post('/sessions',json={'session_name':'  ACS880 5091  '}).json();sid=first['session_id']
    assert first['session_name']=='ACS880 5091'
    assert c.post('/sessions',json={'session_name':'ACS880 5091'}).status_code==201
    assert len(c.get('/sessions').json())==2
    assert c.get('/sessions').headers['cache-control']=='private, no-store'
    assert c.get(f'/sessions/{legacy}').status_code==404
    renamed=c.patch(f'/sessions/{sid}',json={'session_name':'  New name  '})
    assert renamed.status_code==200 and renamed.json()['session_name']=='New name'
    assert c.get('/sessions').json()[0]['id']==sid
    with Session(engine) as db:
        assert str(db.get(EquipmentSession,sid).owner_user_id)==str(a)
    as_user(app,b)
    assert c.get('/sessions').json()==[]
    assert c.get(f'/sessions/{sid}').status_code==404
    assert c.patch(f'/sessions/{sid}',json={'session_name':'Stolen'}).status_code==404
    assert c.get(f'/sessions/{uuid4()}').status_code==404


@pytest.mark.integration
@pytest.mark.parametrize('payload',[{}, {'session_name':''}, {'session_name':'   '},
    {'session_name':'a'*101}, {'session_name':None}, {'session_name':'Case','owner_user_id':str(uuid4())}])
def test_session_name_and_owner_input_validation(owner_api,payload):
    c,app,_,a,_=owner_api;as_user(app,a)
    assert c.post('/sessions',json=payload).status_code==422


@pytest.mark.integration
def test_every_child_route_blocks_other_user_before_provider(owner_api):
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Private case'}).json()['session_id']
    routes=[('GET','/equipment'),('POST','/equipment/identify'),('POST','/equipment/reject'),
        ('POST','/equipment/confirm'),('GET','/images'),('POST','/images'),('POST','/images/analyze-all'),
        ('POST',f'/images/{uuid4()}/analyze'),('GET',f'/images/{uuid4()}/file'),('GET','/visual-findings'),
        ('GET','/visual-context'),('GET','/troubleshooting'),('PUT','/troubleshooting'),
        ('POST','/troubleshooting/run'),('POST','/troubleshooting/follow-up'),('POST','/troubleshooting/symptoms'),
        ('GET',f'/troubleshooting/runs/{uuid4()}'),('GET',f'/troubleshooting/runs/{uuid4()}/sources/{uuid4()}')]
    def forbidden():raise AssertionError('Provider dependency must not run')
    from app.services.vision_provider import get_vision_provider
    from app.services.troubleshooting_provider import get_troubleshooting_provider
    from app.services.equipment_ocr import get_ocr_provider
    for dep in [get_vision_provider,get_troubleshooting_provider,get_ocr_provider]:app.dependency_overrides[dep]=forbidden
    as_user(app,b)
    for method,path in routes:
        assert c.request(method,f'/sessions/{sid}'+path).status_code==404, path
    app.dependency_overrides.pop(auth.require_user)
    for method,path in routes:
        assert c.request(method,f'/sessions/{sid}'+path).status_code==401, path


@pytest.mark.integration
def test_private_images_timestamp_and_readonly_reopen(owner_api):
    c,app,engine,a,b=owner_api;as_user(app,a)
    s=c.post('/sessions',json={'session_name':'Photo'}).json();sid=s['session_id']
    uploaded=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')})
    assert uploaded.status_code==201
    path=f'/sessions/{sid}/images/{uploaded.json()[0]["id"]}/file'
    assert c.get(path).status_code==200
    current=c.get(f'/sessions/{sid}').json();assert current['updated_at']>s['updated_at']
    assert c.get(f'/sessions/{sid}').json()==current
    as_user(app,b);assert c.get(path).status_code==404


@pytest.mark.integration
def test_migration_additive_and_idempotent(owner_api):
    _,_,engine,_,_=owner_api
    legacy=create_session(engine).session_id
    with engine.begin() as c:
        # Recreate only the pre-auth shape inside the isolated test schema.
        c.execute(text('ALTER TABLE equipment_sessions DROP COLUMN owner_user_id CASCADE'))
        c.execute(text('ALTER TABLE equipment_sessions DROP COLUMN session_name'))
    migrate(engine);migrate(engine)
    with Session(engine) as db:
        row=db.get(EquipmentSession,legacy)
        assert row and row.owner_user_id is None and row.session_name is None
    assert user_sessions.list_owned(engine,uuid4())==[]
