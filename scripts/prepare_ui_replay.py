"""Export explicitly labeled, read-only replay data; never export raw LLM audits."""
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'data/evaluation'/name).read_text(encoding='utf-8'))
live=read('step4-live-verifier-review-fix.json')['scenarios'][0]
guard=read('step4-verifier-guard-replay.json')['result']
weak=read('step4-live-fixed.json')['scenarios'][1]
base={'session_id':'recorded-acs880','confirmed_equipment_id':'abb-acs880-01','confirmed_model':'ACS880-01',
      'confirmed_equipment_family':'ACS880','confirmation_status':'CONFIRMED','identification_revision':1,
      'ranked_candidates':[],'mismatch_warnings':[],'confidence':'HIGH','raw_ocr_text':''}
empty={'uploaded_images':[],'aggregated_visual_findings':[],'normalized_visual_findings':[]}
def replay(s,title,final=None):
    final=final or s['run']['result']
    texts={e['chunk_id']:e['chunk_text'] for a in s['run']['audit']['attempts'] for e in a['evidence']}
    trace=dict(s['state_after'],result=final)
    # Select only the UI's needed public state fields, never the full run audit.
    trace={k:trace[k] for k in ('session_id','revision','result','reported_symptoms','follow_up_answers','checks_completed','measurements','retrieved_evidence_history')}
    disclosure='Recorded live OpenAI validation, replayed locally. No fresh model analysis.'
    if title=='ACS880 fault 5091':disclosure+=' The ACS880 answer includes the documented output-role guard replay.'
    return {'title':title,'disclosure':disclosure,
            'equipment':dict(base),'trace':trace,'visual':empty,
            'source_text':{c['chunk_id']:dict(c,chunk_text=texts[c['chunk_id']]) for c in final['sources']}}
acs=replay(live,'ACS880 fault 5091',guard)
low=replay(weak,'Weak-evidence ACS880 example')
photo=read('results-openai-final.json')['results'][0]
manifest=read('manifest.json')['images'][0]
visual=replay(weak,'Recorded visible corrosion')
visual['equipment']=dict(base,session_id='recorded-generic-photo',confirmed_equipment_id=None,confirmed_model=None,
                         confirmed_equipment_family=None,confirmation_status='UNCONFIRMED',confidence=None)
visual['trace']['reported_symptoms']=[]
visual['trace']['result']=dict(visual['trace']['result'],status='not_run',next_question='')
visual['trace']['retrieved_evidence_history']=[]
visual['disclosure']='Recorded visual evidence from a generic electrical-hardware photograph. This is not an ABB identification or a fresh image analysis.'
visual['visual']={'uploaded_images':[{'id':'recorded-photo-01','equipment_id':None,'original_filename':manifest['filename'],
    'view_label':manifest['view_label'],'user_note':None,'analysis_status':'completed'}],
    'aggregated_visual_findings':[dict(f,id=f'recorded-finding-{i}',equipment_id=None,supporting_image_ids=['recorded-photo-01']) for i,f in enumerate(photo['analysis']['findings'])],
    'normalized_visual_findings':[]}
visual['image_urls']={'recorded-photo-01':'/replay-photo-01.jpg'}
visual['attribution']=f"Photo: {manifest['title']} — {manifest['author']}, {manifest['license']}. Source: {manifest['source_page']}. {manifest['modifications']}"
target=ROOT/'frontend/public';target.mkdir(exist_ok=True,parents=True)
(target/'demo.json').write_text(json.dumps({'acs880':acs,'weak':low,'visual':visual},ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(ROOT/'data/evaluation/images'/manifest['filename'],target/'replay-photo-01.jpg')
(target/'REPLAY-PROVENANCE.md').write_text('# Replay provenance\n\nRead-only recorded validation outputs, not fresh analysis.\n\n'+visual['attribution']+
    '\nLicense: '+manifest['license_url']+'\n\nACS880: step4-live-verifier-review-fix.json and documented step4-verifier-guard-replay.json.\nWeak evidence: step4-live-fixed.json.\nVision: results-openai-final.json.\nNo provider prompts, secrets or raw internal audits are exported.\n',encoding='utf-8')
print('Prepared three labeled UI replay records')
