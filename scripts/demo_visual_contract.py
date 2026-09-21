"""Deterministic API contract demo, NOT live vision or photo accuracy evidence."""
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.services.vision_provider import get_vision_provider
from app.services.visual_context import visual_search_request
from app.services.embeddings import get_embedder
from app.services.hybrid_search import search_all
from app.db.session import get_engine


class ContractMock:
    def analyze_equipment_image(self, image, context, *, strict=False):
        findings = [] if context['view_label'] == 'back' else [dict(
            issue_type='dust_buildup', location='ventilation openings',
            description='Visible dust buildup around ventilation openings.',
            severity='medium', visual_confidence='high', bounding_region=None)]
        return {'output': {'image_summary': 'No clear abnormality visible in this image.' if not findings else 'Visible dust around ventilation openings.', 'findings': findings},
                'raw': {'provider': 'DETERMINISTIC CONTRACT MOCK; NOT LIVE VISION'}}


def main():
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32), 'gray').save(buffer, format='PNG')
    app.dependency_overrides[get_vision_provider] = lambda: ContractMock()
    try:
        with TestClient(app) as client:
            created = client.post('/sessions')
            created.raise_for_status()
            sid = created.json()['session_id']
            client.post(f'/sessions/{sid}/equipment/identify', data={'entered_equipment_text': 'ACS880-01'}).raise_for_status()
            confirmed = client.post(f'/sessions/{sid}/equipment/confirm', json={'equipment_id': 'abb-acs880-01'})
            confirmed.raise_for_status()
            uploaded = client.post(f'/sessions/{sid}/images', files=[('images', (name+'.png', buffer.getvalue(), 'image/png')) for name in ['front', 'detail', 'back']],
                data={'view_labels': '["front","close_up","back"]', 'user_notes': '[null,"Noise reported here",null]'})
            uploaded.raise_for_status()
            analyzed = client.post(f'/sessions/{sid}/images/analyze-all')
            analyzed.raise_for_status()
            state = client.get(f'/sessions/{sid}/visual-findings').json()
            context = client.get(f'/sessions/{sid}/visual-context').json()
            assert client.get(f'/sessions/{sid}/equipment').json() == confirmed.json()
            request, omitted = visual_search_request(context, get_embedder())
            evidence = search_all(get_engine(), request, get_embedder())
            report = dict(label='DETERMINISTIC MOCK VISION / SYNTHETIC IMAGE CONTRACT DEMO; real PostgreSQL and ABB retrieval',
                session_id=sid, uploaded=uploaded.json(), analyzed=analyzed.json(), state=state,
                visual_context=context, retrieval_request=request.model_dump(mode='json'), omitted_finding_ids=omitted,
                real_corpus_evidence=[e.model_dump(mode='json') for e in evidence['hybrid']],
                confirmed_equipment_preserved=True)
            path = ROOT / 'data/processed/visual-contract-demo.json'
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(f'Contract demo stored: {path}; session {sid}; {len(evidence["hybrid"])} real corpus results')
    finally:
        app.dependency_overrides.pop(get_vision_provider, None)


if __name__ == '__main__':
    main()
