"""Deterministic Step 4 demo: real corpus retrieval, simulated inputs and LLM.

Temporary session schema is isolated from production. No OCR, vision or paid LLM
calls. Mock judgments below are scenario fixtures, NOT a verifier accuracy claim.
"""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4, UUID
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import get_settings
from app.db.session import get_engine
from app.db.init_equipment import initialize_equipment
from app.db.init_vision import initialize_vision
from app.db.init_troubleshooting import initialize_troubleshooting
from app.models.equipment import Equipment, EquipmentSession
from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding
from app.services.visual_aggregation import aggregate
from app.services.embeddings import get_embedder
from app.services.troubleshooting_query import retrieve
from app.services import troubleshooting_sessions as sessions
from app.schemas.troubleshooting import TroubleshootingInput

DIRT = 'dirt, which drifts into the machine, causes contamination and reduces the efficiency of the cooling.'
TEMP = 'elevated ambient temperature or high intake air temperature'
CLAIM = 'For open-air cooling, dirt entering the machine reduces cooling efficiency.'
LABEL = 'Possible reduced cooling efficiency from dirt in an open-air-cooled machine.'
RATIONALE = 'The open-air cooling section identifies dirt contamination as reducing cooling efficiency.'
ALT = 'Possible elevated ambient or intake air temperature.'
ALT_REASON = 'The same open-air cooling section lists elevated ambient or intake air temperature as other possible causes of poor cooling performance.'


class DemoLLM:
    """All accepted statements require actual retrieved supporting text."""
    def complete(self, stage, payload):
        if stage == 'review':
            ratings = []
            for e in payload['evidence']:
                relevant = ('7.8.1 ' in (e['section_title'] or '') and (DIRT in ' '.join(e['chunk_text'].split()) or TEMP in e['chunk_text'])) or e['section_title'] == '7.8 Maintenance of cooling units'
                ratings.append(dict(chunk_id=e['chunk_id'], relevance='RELEVANT' if relevant else 'NOT_RELEVANT',
                    issue='open-air cooling', reason='Scenario fixture: applicable open-air cooling text' if relevant else 'Outside this bounded fixture'))
            output = dict(chunks=ratings, strength='STRONG' if sum(r['relevance'] == 'RELEVANT' for r in ratings) >= 2 else 'WEAK',
                          missing_information=['Recorded operating temperature and exact model are missing'])
        elif stage == 'conflict':
            assert len(payload['evidence']) in (2, 3)
            assert all((e['section_title'] or '').startswith(('7.8.1 ', '7.8 ')) for e in payload['evidence'])
            output = dict(relationship='COMPLEMENTARY', chunk_ids=[e['chunk_id'] for e in payload['evidence']],
                          explanation='Same manual: general cooling-unit condition and open-air cooling contamination passages are complementary.')
        elif stage == 'candidate':
            dirt = next(e for e in payload['evidence'] if DIRT in ' '.join(e['chunk_text'].split()))
            temp = next((e for e in payload['evidence'] if TEMP in e['chunk_text']), None)
            output = dict(primary_cause=dict(label=LABEL, rationale=RATIONALE, claim_ids=['cooling-dirt']),
                alternative_causes=[dict(label=ALT, rationale=ALT_REASON, claim_ids=['cooling-temperature'])] if temp else [],
                technical_claims=[dict(claim_id='cooling-dirt', text=CLAIM, citation_chunk_ids=[dirt['chunk_id']])] +
                    ([dict(claim_id='cooling-temperature', text=ALT, citation_chunk_ids=[temp['chunk_id']])] if temp else []),
                recommended_actions=[], next_question=None,
                missing_information=['Recorded operating temperature and exact model are missing'])
        else:
            claim = payload['claim']
            required = DIRT if claim in (CLAIM, LABEL, RATIONALE) else TEMP if claim in (ALT, ALT_REASON) else None
            supported = required is not None and any(required in ' '.join(e['chunk_text'].split()) for e in payload['evidence'])
            output = dict(status='SUPPORTED' if supported else 'UNSUPPORTED', revised_text=None,
                          explanation='Deterministic fixture: required supporting passage present in explicitly cited evidence' if supported else 'Not in this bounded fixture')
        return dict(output=output, raw={'provider': 'deterministic-demo-fixture', 'live_llm': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/evaluation/step4-demo.json')
    args = parser.parse_args()
    settings, real_engine, embedder = get_settings(), get_engine(), get_embedder()
    schema = 'demo_step4_' + uuid4().hex
    with real_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(settings.database_url, connect_args={'options': f'-csearch_path={schema},public'})
    engine = engine.execution_options(schema_translate_map={None: schema})
    try:
        initialize_equipment(engine); initialize_vision(engine); initialize_troubleshooting(engine)
        sid, image_id, fid = uuid4(), uuid4(), uuid4()
        with Session(engine) as db, db.begin():
            db.add(Equipment(id='demo-motor', manufacturer='ABB', equipment_family='Induction Motors and Generators',
                model_name='induction motor', model_number_pattern='demo-only', product_type='motor', aliases=[],
                source_url='https://library.abb.com/', retrieval_model='', retrieval_family='Induction Motors and Generators'))
            db.flush()
            db.add(EquipmentSession(id=sid, confirmed_equipment_id='demo-motor', selected_candidate='demo-motor',
                confirmation_status='CONFIRMED', identification_revision=1))
            db.flush()
            db.add(SessionImage(id=image_id, session_id=sid, equipment_id='demo-motor', view_label='front',
                original_filename='SIMULATED-NO-PHOTO', stored_path='SIMULATED-NO-FILE', mime_type='image/png',
                analysis_status='completed', raw_vision_results=[{'simulated': True}]))
            db.flush()
            db.add(VisualFinding(id=fid, session_id=sid, image_id=image_id, issue_type='dust_buildup',
                location='cooling ventilation openings', description='Heavy dust and dirt on cooling ventilation openings',
                severity='medium', visual_confidence='high', source='deterministic_demo_fixture'))
            db.flush()
            for item in aggregate([dict(id=fid, session_id=sid, image_id=image_id, equipment_id='demo-motor',
                issue_type='dust_buildup', location='cooling ventilation openings',
                description='Heavy dust and dirt on cooling ventilation openings', severity='medium', visual_confidence='high')], sid):
                db.add(AggregatedVisualFinding(**item))
        inputs = TroubleshootingInput(reported_symptoms=['Motor overheating'],
            confirmed_observations=['Open-air cooling design confirmed in project documentation'])
        sessions.update(engine, sid, inputs)
        final = sessions.run(engine, sid, DemoLLM(), embedder, settings,
                             lambda plan: retrieve(real_engine, plan, embedder, settings))
        run_id = UUID(final['retrieved_evidence_history'][-1]['run_id'])
        run = sessions.get_run(engine, sid, run_id, include_evidence=True)
        report = dict(title='Step 4 deterministic motor troubleshooting demo',
            disclosure='Real ABB corpus retrieval. Equipment confirmation, open-air design, dust finding and LLM judgments are simulated. No photo or live diagnostic LLM evaluated. Temporary session schema removed after run.',
            model='deterministic-demo-fixture', input=inputs.model_dump(), **run)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        for index, attempt in enumerate(run['audit']['attempts'], 1):
            print(f'Attempt {index}: contextual query\n' + json.dumps(attempt['query'], indent=2))
            print('Retrieved real evidence:')
            for e in attempt['evidence']:
                print(f"  {e['chunk_id']} | {e['document_title']} | physical p.{e['page_number']} | {e['section_title']}")
            print('Conflict result:', json.dumps(attempt.get('conflicts', [])))
            print('Generated candidate:', json.dumps(attempt.get('candidate'), indent=2))
            print('Claim verification:', json.dumps(attempt['verifications'], indent=2))
        print('Final technician response:', json.dumps(run['result'], indent=2))
        print('Full retrieval text and audit saved to', args.output)
        if run['result']['status'] != 'suspected_cause':
            raise SystemExit('Demo did not find its expected supporting real passages; inspect report')
    finally:
        engine.dispose()
        with real_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


if __name__ == '__main__':
    main()
