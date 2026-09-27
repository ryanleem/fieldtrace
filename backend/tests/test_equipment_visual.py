import json
import httpx
import pytest
from app.config import Settings
from app.services.equipment_visual import EquipmentVisualProvider
from app.services.vision_provider import OpenAIVisionProvider, GeminiVisionProvider
from app.services.equipment_fusion import fuse_identity
from app.services.equipment_sessions import create_session, identify, get_state, confirm
from app.schemas.equipment import ConfirmEquipment
from test_equipment import CATALOG, ocr_observation, MockOCR, image_bytes, equipment_db


def observation(index=0,family='ACS880',confidence='MEDIUM'):
    return dict(image_index=index,observed_text='',observed_features=['Distinctive panel and vent arrangement'],
                candidate_manufacturer='ABB',candidate_family=family,candidate_model='ACS880-01-FAKE-SKU',confidence=confidence)


def test_visual_only_is_family_and_never_exact_type():
    for views,level in [([observation()], 'LOW'),([observation(),observation(1)],'MEDIUM')]:
        result=fuse_identity('',[],CATALOG,{'images':views})
        summary=result['identification_evidence']['summary']
        assert summary['specificity']=='model_family' and summary['confidence']==level
        assert 'ACS880 family' in summary['label'] and 'FAKE' not in summary['label']
        assert not summary['exact_type_confirmed'] and not result['ranked_candidates']


def test_visual_conflict_and_unsupported_family_abstain():
    for views in [[observation(),observation(1,'ACS580')],[observation(family='Unsupported')]]:
        result=fuse_identity('',[],CATALOG,{'images':views})
        assert result['identification_evidence']['summary']['specificity']=='insufficient'
    assert fuse_identity('',[],CATALOG,{'images':[observation(),observation(1,'ACS580')]})['mismatch_warnings']


def test_partial_ocr_narrows_family_and_blocks_subtype_confirmation():
    result=fuse_identity('',[ocr_observation('ABB ACS88')],CATALOG,{'images':[observation()]})
    summary=result['identification_evidence']['summary']
    assert summary['specificity']=='model_family' and summary['confidence']=='MEDIUM'
    assert all(not c['confirmable'] for c in result['ranked_candidates'])
    result=fuse_identity('',[ocr_observation('ABB ACS880')],CATALOG)
    assert result['identification_evidence']['summary']['specificity']=='model_family'


def test_strong_nameplate_wins_and_remains_exact_with_conflict():
    result=fuse_identity('ACS580-01',[ocr_observation()],CATALOG,{'images':[observation()]})
    assert result['ranked_candidates'][0]['candidate_id']=='abb-acs880-01'
    assert result['mismatch_warnings']
    assert result['identification_evidence']['summary']['label']=='ABB ACS880-01-07A2-3'
    plain=fuse_identity('',[ocr_observation()],CATALOG)
    assert plain['identification_evidence']['summary']['confidence']=='HIGH'


def test_brand_only_requires_readable_brand():
    obs=observation(family=None);obs['observed_text']='ABB'
    assert fuse_identity('',[],CATALOG,{'images':[obs]})['identification_evidence']['summary']['specificity']=='manufacturer'
    obs['observed_text']=''
    assert fuse_identity('',[],CATALOG,{'images':[obs]})['identification_evidence']['summary']['specificity']=='insufficient'


@pytest.mark.parametrize('vendor',['openai','gemini'])
def test_multiview_wire_contract_and_schema(vendor):
    from app.services.vision_provider import VisionImage
    def handler(request):
        body=json.loads(request.content)
        if vendor=='openai':
            assert len(body['input'][0]['content'])==3
            assert body['text']['format']['schema']['properties']['images']
            return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'images':[observation(),observation(1)]})}]}]})
        assert len(body['contents'][0]['parts'])==3
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'images':[observation(),observation(1)]})}]}}]})
    settings=Settings(_env_file=None,openai_api_key='fixture',gemini_api_key='fixture')
    adapter=(OpenAIVisionProvider if vendor=='openai' else GeminiVisionProvider)(settings,httpx.MockTransport(handler))
    output=EquipmentVisualProvider(adapter).extract([VisionImage(image_bytes(),'image/png')]*2,CATALOG,[])
    assert len(output['images'])==2


@pytest.mark.integration
def test_cache_multi_photo_fusion_persistence_and_confirmation_gate(equipment_db):
    engine=equipment_db;sid=create_session(engine).session_id
    calls=[]
    class Visual:
        def extract(self,images,catalog,ocr):
            calls.append(len(images));return {'images':[observation(i) for i in range(len(images))]}
    class OCR(MockOCR):
        def extract(self,image):
            calls.append('ocr');return super().extract(image)
    images=[{'data':image_bytes()+extra,'role':'equipment'} for extra in (b'',b'other')]
    first=identify(engine,sid,'',images,OCR(''),Visual())
    assert first.identification['confidence']=='MEDIUM' and calls==['ocr','ocr',2]
    assert get_state(engine,sid).identification==first.identification
    identify(engine,sid,'unknown',images,OCR(''),Visual())
    assert calls==['ocr','ocr',2]
    partial=identify(engine,sid,'',[{'data':image_bytes()+b'partial','role':'nameplate'}],MockOCR('ACS880'),Visual())
    with pytest.raises(ValueError,match='Family-level'):
        confirm(engine,sid,ConfirmEquipment(equipment_id='abb-acs880-01'))


@pytest.mark.integration
def test_clear_plate_skips_visual_provider_and_failure_preserves_ocr(equipment_db):
    sid=create_session(equipment_db).session_id
    class Broken:
        def extract(self,*args):raise RuntimeError('private provider response')
    state=identify(equipment_db,sid,'',[{'data':image_bytes(),'role':'nameplate'}],MockOCR(),Broken())
    assert state.identification['specificity']=='exact_type' and 'provider_error' not in state.identification
    state=identify(equipment_db,sid,'',[{'data':image_bytes()+b'partial','role':'nameplate'}],MockOCR('ACS880'),Broken())
    assert state.identification['specificity']=='model_family' and 'provider_error' in state.identification
    assert 'private provider' not in str(state.model_dump())


@pytest.mark.parametrize('output',[{'images':[observation(8)]},{'images':[observation(),observation()]},{'images':[]},{'images':[dict(observation(),confidence='99%')]}])
def test_malformed_or_misindexed_provider_evidence_is_rejected(output):
    from app.services.vision_provider import VisionImage
    class Adapter:
        def analyze_equipment_image(self,*args,**kwargs):return {'output':output}
    with pytest.raises(ValueError):
        EquipmentVisualProvider(Adapter()).extract([VisionImage(image_bytes(),'image/png')],CATALOG,[])


@pytest.mark.integration
def test_duplicate_views_do_not_raise_visual_confidence(equipment_db):
    sid=create_session(equipment_db).session_id
    class Visual:
        def extract(self,images,*args):
            assert len(images)==1
            return {'images':[observation()]}
    result=identify(equipment_db,sid,'',[{'data':image_bytes(),'role':'equipment'}]*2,MockOCR(''),Visual())
    assert result.identification['confidence']=='LOW'
    assert len(result.ocr_results)==1


def test_generic_catalog_visual_matching_does_not_require_acs880():
    row={**CATALOG[0], 'id':'future','manufacturer':'Example','equipment_family':'ZX900','model_name':'ZX900-02','aliases':[]}
    obs={**observation(),'candidate_manufacturer':'Example','candidate_family':'ZX900','candidate_model':None}
    result=fuse_identity('',[],[row],{'images':[obs]})
    assert result['identification_evidence']['summary']['label']=='Likely Example ZX900 family'
