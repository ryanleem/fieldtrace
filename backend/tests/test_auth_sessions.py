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
    monkeypatch.setattr(equipment,'get_settings',lambda:settings)
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


@pytest.mark.integration
def test_delete_owner_cascades_and_preserves_other_data(owner_api):
    from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding
    from app.models.troubleshooting import TroubleshootingSession, TroubleshootingRun
    from app.models.equipment import Equipment
    from sqlalchemy import select, func
    from pathlib import Path
    c,app,engine,a,b=owner_api
    as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Delete fixture only'}).json()['session_id']
    other=c.post('/sessions',json={'session_name':'Keep'}).json()['session_id']
    image=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')}).json()[0]
    other_image=c.post(f'/sessions/{other}/images',files={'images':('keep.png',image_bytes(),'image/png')}).json()[0]
    from uuid import UUID
    with Session(engine) as db, db.begin():
        path=equipment.get_settings().uploads_dir/db.get(SessionImage,image['id']).stored_path
        other_path=equipment.get_settings().uploads_dir/db.get(SessionImage,other_image['id']).stored_path
        catalog_count=db.scalar(select(func.count()).select_from(Equipment))
        fid=uuid4()
        db.add(VisualFinding(id=fid,session_id=UUID(sid),image_id=UUID(image['id']),issue_type='corrosion',location='housing',description='Visible corrosion',severity='low',visual_confidence='high'))
        db.add(AggregatedVisualFinding(id=uuid4(),session_id=UUID(sid),issue_type='corrosion',location='housing',description='Visible corrosion',severity='low',visual_confidence='high',supporting_image_ids=[image['id']],supporting_finding_ids=[str(fid)]))
        db.add(TroubleshootingSession(session_id=UUID(sid),equipment_revision=0,inputs={'measurements':[{'value':1}],'checks_completed':['test'],'follow_up_answers':['test']}))
        db.add(TroubleshootingRun(session_id=UUID(sid),input_revision=0,equipment_revision=0,context_fingerprint='fixture',status='not_run',audit={'retrieved_evidence':[]},final={'sources':[]}))
    as_user(app,b)
    assert c.delete(f'/sessions/{sid}').status_code==404
    assert path.exists()
    app.dependency_overrides.pop(auth.require_user)
    assert c.delete(f'/sessions/{sid}').status_code==401
    as_user(app,a)
    legacy=create_session(engine).session_id
    for target in [legacy,uuid4()]:assert c.delete(f'/sessions/{target}').status_code==404
    response=c.delete(f'/sessions/{sid}')
    assert response.status_code==200 and response.json()=={'deleted':True,'file_cleanup_pending':False}
    assert not path.exists() and other_path.exists()
    with Session(engine) as db:
        assert db.get(EquipmentSession,sid) is None
        assert db.get(EquipmentSession,other) is not None
        assert db.get(EquipmentSession,legacy) is not None
        for model in [SessionImage,VisualFinding,AggregatedVisualFinding,TroubleshootingSession,TroubleshootingRun]:
            assert db.scalar(select(func.count()).select_from(model).where(model.session_id==UUID(sid)))==0
        assert db.scalar(select(func.count()).select_from(Equipment))==catalog_count
    assert c.delete(f'/sessions/{sid}').status_code==404


@pytest.mark.integration
@pytest.mark.parametrize('mode',['outside','other_session','missing','permission'])
def test_delete_file_cleanup_is_scoped_and_failure_is_reported(owner_api,tmp_path,monkeypatch,mode):
    from app.models.vision import SessionImage
    from pathlib import Path
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Cleanup fixture'}).json()['session_id']
    image=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')}).json()[0]
    root=equipment.get_settings().uploads_dir
    unrelated=tmp_path/'must-keep.png';unrelated.write_bytes(b'keep')
    with Session(engine) as db,db.begin():
        record=db.get(SessionImage,image['id']);actual=root/record.stored_path
        if mode=='outside':record.stored_path=str(unrelated)
        if mode=='other_session':record.stored_path=f'{uuid4()}/{image["id"]}.png'
    if mode=='missing':actual.unlink()
    if mode=='permission':
        original=Path.unlink
        def denied(path,*args,**kwargs):
            if path==actual:raise PermissionError('private filesystem detail')
            return original(path,*args,**kwargs)
        monkeypatch.setattr(Path,'unlink',denied)
    result=c.delete(f'/sessions/{sid}')
    assert result.status_code==200
    assert result.json()['file_cleanup_pending']==(mode!='missing')
    assert 'private filesystem' not in result.text
    assert unrelated.read_bytes()==b'keep'
    assert c.get(f'/sessions/{sid}').status_code==404


@pytest.mark.integration
def test_delete_transaction_failure_does_not_remove_files(owner_api,monkeypatch):
    from app.models.vision import SessionImage
    from sqlalchemy import event
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Rollback fixture'}).json()['session_id']
    image=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')}).json()[0]
    with Session(engine) as db:path=equipment.get_settings().uploads_dir/db.get(SessionImage,image['id']).stored_path
    def reject_commit(session):raise RuntimeError('Test rollback')
    event.listen(Session,'before_commit',reject_commit)
    try:
        with pytest.raises(RuntimeError,match='Test rollback'):
            user_sessions.delete_owned(engine,sid,a,equipment.get_settings())
    finally:event.remove(Session,'before_commit',reject_commit)
    assert path.exists()
    assert c.get(f'/sessions/{sid}').status_code==200


@pytest.mark.integration
def test_delete_rejects_redirected_session_directory(owner_api,tmp_path,monkeypatch):
    from pathlib import Path
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Redirect fixture'}).json()['session_id']
    image=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')}).json()[0]
    directory=equipment.get_settings().uploads_dir.resolve()/sid
    # Portable simulation of a junction/symlink resolution, no Windows symlink privilege needed.
    original=Path.resolve
    def redirected(path,*args,**kwargs):
        if path==directory:return tmp_path
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'resolve',redirected)
    result=c.delete(f'/sessions/{sid}')
    assert result.status_code==200 and result.json()['file_cleanup_pending']
    assert (directory/(image['id']+'.png')).exists()


@pytest.mark.integration
def test_draft_saving_owner_scoped_idempotent_and_no_reasoning(owner_api):
    from app.models.troubleshooting import TroubleshootingSession
    from app.services.troubleshooting_sessions import snapshot, fingerprint
    from app.schemas.troubleshooting import TroubleshootingInput
    from app.services import troubleshooting_sessions
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Draft fixture'}).json()['session_id']
    payload={'model':'ABB ACS880-01','symptom':'Fault 5091','followup':'Fan running',
             'entry_type':'measurement','measurement':{'name':'temperature','value':'','unit':'C','location':'housing'}}
    for method in ['get','put']:
        as_user(app,b)
        assert getattr(c,method)(f'/sessions/{sid}/draft',**({'json':payload} if method=='put' else {})).status_code==404
    app.dependency_overrides.pop(auth.require_user)
    assert c.put(f'/sessions/{sid}/draft',json=payload).status_code==401
    as_user(app,a)
    c.get(f'/sessions/{sid}/troubleshooting')
    with Session(engine) as db:
        owner=db.get(EquipmentSession,sid);row=db.get(TroubleshootingSession,sid)
        revision=row.revision;before=fingerprint(snapshot(db,owner,row))
    for _ in range(2):assert c.put(f'/sessions/{sid}/draft',json=payload).json()==payload
    assert c.get(f'/sessions/{sid}/draft').json()==payload
    with Session(engine) as db:
        owner=db.get(EquipmentSession,sid);row=db.get(TroubleshootingSession,sid)
        assert row.revision==revision and fingerprint(snapshot(db,owner,row))==before
        assert owner.entered_equipment_text is None and owner.confirmed_equipment_id is None
        assert row.inputs['reported_symptoms']==[] and row.inputs['follow_up_answers']==[]
        assert db.scalar(text('SELECT count(*) FROM troubleshooting_runs'))==0
    assert c.put(f'/sessions/{sid}/draft',json={**payload,'owner_user_id':str(b)}).status_code==422
    assert c.put(f'/sessions/{sid}/draft',json={**payload,'symptom':'x'*1201}).status_code==422
    assert c.get(f'/sessions/{sid}/draft').json()==payload
    troubleshooting_sessions.update(engine,sid,TroubleshootingInput(reported_symptoms=['Fault 5091']))
    assert c.get(f'/sessions/{sid}/draft').json()==payload
    payload['symptom']=''
    assert c.put(f'/sessions/{sid}/draft',json=payload).status_code==200
    assert c.get(f'/sessions/{sid}/draft').json()['symptom']==''


@pytest.mark.integration
def test_image_content_retry_is_scoped_and_preserves_metadata(owner_api):
    import hashlib
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Image retry fixture'}).json()['session_id']
    content=image_bytes()
    def send(session,filename='same.png',data=content,note='Latest queued note'):
        return c.post(f'/sessions/{session}/images',files={'images':(filename,data,'image/png')},data={'user_notes':__import__('json').dumps([note])})
    # Treat the first successful response as lost; retry with identical original bytes.
    first=send(sid).json()[0]
    retry=send(sid,'renamed.png',note='Must not overwrite saved note').json()[0]
    assert first['id']==retry['id'] and retry['user_note']=='Latest queued note'
    assert retry['content_sha256']==hashlib.sha256(content).hexdigest()
    second=send(sid,data=content+b'different').json()[0]
    assert second['id']!=first['id']
    assert len(c.get(f'/sessions/{sid}/images').json())==2
    as_user(app,b)
    assert c.get(f'/sessions/{sid}/images').status_code==404
    assert send(sid).status_code==404
    other=c.post('/sessions',json={'session_name':'Other owner'}).json()['session_id']
    own=send(other).json()[0]
    assert own['id']!=first['id'] and own['content_sha256']==first['content_sha256']
    assert len(c.get(f'/sessions/{other}/images').json())==1


@pytest.mark.integration
def test_remove_photo_cascades_rebuilds_aggregates_and_enforces_owner(owner_api):
    from app.services import inspection_images
    from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding
    from test_vision import MockVision
    from sqlalchemy import select
    from uuid import UUID
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Remove image fixture'}).json()['session_id']
    photos=[c.post(f'/sessions/{sid}/images',files={'images':('same.png',image_bytes()+extra,'image/png')}).json()[0] for extra in [b'',b'other']]
    for photo in photos:inspection_images.analyze_image(engine,UUID(sid),UUID(photo['id']),MockVision(),equipment.get_settings())
    with Session(engine) as db:
        paths=[equipment.get_settings().uploads_dir/db.get(SessionImage,p['id']).stored_path for p in photos]
    target=f'/sessions/{sid}/images/{photos[0]["id"]}'
    as_user(app,b);assert c.delete(target).status_code==404
    app.dependency_overrides.pop(auth.require_user);assert c.delete(target).status_code==401
    as_user(app,a)
    assert c.delete(f'/sessions/{sid}/images/{uuid4()}').status_code==404
    assert c.delete(target).json()=={'deleted':True,'file_cleanup_pending':False}
    assert not paths[0].exists() and paths[1].exists()
    state=c.get(f'/sessions/{sid}/visual-findings').json()
    assert len(state['uploaded_images'])==len(state['normalized_visual_findings'])==1
    assert state['aggregated_visual_findings'][0]['supporting_image_ids']==[photos[1]['id']]
    # Same owner, wrong session/image pairing must also fail.
    other=c.post('/sessions',json={'session_name':'Other case'}).json()['session_id']
    assert c.delete(f'/sessions/{other}/images/{photos[1]["id"]}').status_code==404


@pytest.mark.integration
def test_legacy_image_hash_migration_preserves_duplicates_and_retry_reuses(owner_api):
    from app.db.migrate_image_fingerprints import migrate as migrate_hashes
    from app.models.vision import SessionImage
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Legacy fixture'}).json()['session_id']
    rows=[c.post(f'/sessions/{sid}/images',files={'images':('legacy.png',image_bytes()+extra,'image/png')}).json()[0] for extra in [b'',b'other']]
    with Session(engine) as db,db.begin():
        for item in rows:
            row=db.get(SessionImage,item['id']);row.content_sha256=None
            (equipment.get_settings().uploads_dir/row.stored_path).write_bytes(image_bytes())
    migrate_hashes(engine);migrate_hashes(engine)
    retry=c.post(f'/sessions/{sid}/images',files={'images':('retry.png',image_bytes(),'image/png')}).json()[0]
    assert retry['id'] in [r['id'] for r in rows]
    assert len(c.get(f'/sessions/{sid}/images').json())==2


@pytest.mark.integration
def test_remove_photo_refuses_unrelated_stored_path(owner_api,tmp_path):
    from app.models.vision import SessionImage
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Unsafe path fixture'}).json()['session_id']
    row=c.post(f'/sessions/{sid}/images',files={'images':('photo.png',image_bytes(),'image/png')}).json()[0]
    unrelated=tmp_path/'unrelated.png';unrelated.write_bytes(b'keep')
    with Session(engine) as db,db.begin():db.get(SessionImage,row['id']).stored_path=str(unrelated)
    result=c.delete(f'/sessions/{sid}/images/{row["id"]}')
    assert result.status_code==200 and result.json()['file_cleanup_pending']
    assert unrelated.read_bytes()==b'keep'


@pytest.mark.integration
def test_concurrent_and_same_batch_image_retries_reuse_one_file(owner_api):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import UUID
    from app.services.inspection_images import upload_images
    from app.models.vision import SessionImage
    from sqlalchemy import select
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=UUID(c.post('/sessions',json={'session_name':'Concurrent uploads'}).json()['session_id'])
    settings=equipment.get_settings()
    upload={'data':image_bytes(),'original_filename':'same.png'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:upload_images(engine,sid,[upload,upload],settings),range(2)))
    assert len({str(row['id']) for result in results for row in result})==1
    with Session(engine) as db:
        rows=list(db.scalars(select(SessionImage).where(SessionImage.session_id==sid)))
        assert len(rows)==1
    assert len(list((settings.uploads_dir/str(sid)).iterdir()))==1


@pytest.mark.integration
def test_saved_nameplate_identification_is_owner_scoped_and_ignores_symptoms(owner_api):
    from app.services.equipment_ocr import get_ocr_provider
    from test_equipment import MockOCR
    c,app,engine,a,b=owner_api;as_user(app,a)
    app.dependency_overrides[get_ocr_provider]=lambda:MockOCR()
    sid=c.post('/sessions',json={'session_name':'Saved plate'}).json()['session_id']
    image=c.post(f'/sessions/{sid}/images',files={'images':('plate.png',image_bytes(),'image/png')},data={'view_labels':'["nameplate"]'}).json()[0]
    import json
    for symptom in ['not sure','unknown','',"won't run"]:
        c.put(f'/sessions/{sid}/draft',json={'model':'','symptom':symptom})
        result=c.post(f'/sessions/{sid}/equipment/identify',data={'entered_equipment_text':symptom,'saved_image_ids':json.dumps([image['id']])})
        assert result.status_code==200
        assert result.json()['ranked_candidates'][0]['candidate_id']=='abb-acs880-01'
        assert not result.json()['mismatch_warnings']
    conflict=c.post(f'/sessions/{sid}/equipment/identify',data={'entered_equipment_text':'ACS580-01','saved_image_ids':json.dumps([image['id']])}).json()
    assert conflict['ranked_candidates'][0]['candidate_id']=='abb-acs880-01' and conflict['mismatch_warnings']
    as_user(app,b)
    other=c.post('/sessions',json={'session_name':'Other user'}).json()['session_id']
    assert c.post(f'/sessions/{other}/equipment/identify',data={'saved_image_ids':json.dumps([image['id']])}).status_code==404
    assert c.post(f'/sessions/{sid}/equipment/identify',data={'saved_image_ids':json.dumps([image['id']])}).status_code==404


@pytest.mark.integration
@pytest.mark.parametrize('payload,field', [({'answer':'STO wiring has not yet been checked.'},'follow_up_answers'), ({'checks_completed':['STO wiring inspected']},'checks_completed'), ({'measurements':[{'name':'temperature','value':'42','unit':'C','location':'housing'}]},'measurements')])
def test_followup_endpoint_persists_each_update_before_reasoning(owner_api,monkeypatch,payload,field):
    from app.services import troubleshooting_sessions
    c,app,engine,a,b=owner_api;as_user(app,a)
    sid=c.post('/sessions',json={'session_name':'Update persistence'}).json()['session_id']
    calls=[]
    def run(engine,session_id,*args):
        state=troubleshooting_sessions.get_state(engine,session_id)
        calls.append(state)
        return state
    monkeypatch.setattr(troubleshooting_sessions,'run',run)
    app.dependency_overrides[troubleshooting.get_troubleshooting_provider]=lambda:object()
    app.dependency_overrides[troubleshooting.get_embedder]=lambda:object()
    result=c.post(f'/sessions/{sid}/troubleshooting/follow-up',json=payload)
    assert result.status_code==200 and len(calls)==1
    assert result.json()[field] and calls[0][field]==result.json()[field]
    assert c.get(f'/sessions/{sid}/troubleshooting').json()[field]==result.json()[field]
    as_user(app,b)
    assert c.post(f'/sessions/{sid}/troubleshooting/follow-up',json=payload).status_code==404
    assert len(calls)==1


@pytest.mark.integration
def test_identification_photo_selection_persists_and_is_owner_scoped(owner_api):
    from app.services.equipment_ocr import get_ocr_provider
    from test_equipment import MockOCR
    from app.db.migrate_identification_evidence import migrate as migrate_identity
    c,app,engine,a,b=owner_api;as_user(app,a)
    app.dependency_overrides[get_ocr_provider]=lambda:MockOCR()
    sid=c.post('/sessions',json={'session_name':'Identification selection'}).json()['session_id']
    photo=c.post(f'/sessions/{sid}/images',files={'images':('front.png',image_bytes(),'image/png')},data={'view_labels':'["front"]','identification_flags':'[true]'}).json()[0]
    assert photo['use_for_identification'] is True
    migrate_identity(engine);migrate_identity(engine)
    assert c.get(f'/sessions/{sid}/images').json()[0]['use_for_identification'] is True
    state=c.post(f'/sessions/{sid}/equipment/identify').json()
    assert state['ranked_candidates'][0]['candidate_id']=='abb-acs880-01'
    path=f'/sessions/{sid}/images/{photo["id"]}/identification'
    as_user(app,b)
    assert c.patch(path,json={'use_for_identification':False}).status_code==404
    as_user(app,a)
    assert c.patch(path,json={'use_for_identification':False}).json()['use_for_identification'] is False
    assert len(c.get(f'/sessions/{sid}/images').json())==1
    assert c.post(f'/sessions/{sid}/equipment/identify').json()['ranked_candidates']==[]
