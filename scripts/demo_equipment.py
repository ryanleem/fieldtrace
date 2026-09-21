"""Step 2 demonstration: synthetic test image, confirmation, then explicit evidence search.

Default: actual local OCR. --mock-ocr: deterministic provider replacement for tests.
Never claims the fixture is a real ABB nameplate or verifies a manufactured SKU.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.services.equipment_ocr import OCRResult, get_ocr_provider

FIXTURE_TEXT = 'ABB\nTYPE: ACS880-01-07A2-3\n400 V\n7.2 A\n3 kW\n50 Hz\nSERIAL: DEMO123456'


class DemoOCR:
    def extract(self, image):
        return OCRResult(FIXTURE_TEXT, 'mock-demo-fixture')


def make_fixture():
    image = Image.new('RGB', (1400, 900), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=48)
    small = ImageFont.load_default(size=30)
    draw.text((40, 25), 'SYNTHETIC OCR TEST - NOT AN ABB NAMEPLATE', font=small, fill='black')
    for index, line in enumerate(FIXTURE_TEXT.splitlines()):
        draw.text((70, 110 + index * 90), line, font=font, fill='black')
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mock-ocr', action='store_true')
    args = parser.parse_args()
    if args.mock_ocr:
        app.dependency_overrides[get_ocr_provider] = lambda: DemoOCR()
    fixture = make_fixture()
    folder = ROOT / 'data/processed'
    folder.mkdir(exist_ok=True)
    (ROOT / 'work').mkdir(exist_ok=True)
    (ROOT / 'work/synthetic-nameplate-demo.png').write_bytes(fixture)
    try:
        with TestClient(app) as client:
            response = client.post('/sessions')
            response.raise_for_status()
            initial = response.json()
            path = f"/sessions/{initial['session_id']}/equipment"
            response = client.post(path + '/identify', data={'entered_equipment_text': 'ACS580', 'image_roles': '["nameplate"]'},
                                   files=[('images', ('synthetic-demo.png', fixture, 'image/png'))])
            response.raise_for_status()
            identified = response.json()
            assert identified['ranked_candidates'][0]['candidate_id'] == 'abb-acs880-01', identified
            assert identified['mismatch_warnings'] and identified['confirmed_equipment_id'] is None
            response = client.post(path + '/confirm', json={'equipment_id': 'abb-acs880-01',
                                  'identification_revision': identified['identification_revision']})
            response.raise_for_status()
            confirmed = response.json()
            persisted = client.get(path).json()
            assert persisted['confirmed_equipment_id'] == 'abb-acs880-01'
            # Separate explicit search call; identification does not run retrieval.
            response = client.post('/search', json={'query': 'fault tracing', 'top_k': 5, **confirmed['retrieval_filters']})
            response.raise_for_status()
            evidence = response.json()
            assert len(evidence['results']) == 5
            assert all(item['equipment_model'] == 'ACS880' for item in evidence['results'])
            report = {'fixture_notice': 'Synthetic OCR test fixture, not a real nameplate or a validated SKU specification.',
                      'ocr_mode': 'mock' if args.mock_ocr else 'real-local-rapidocr',
                      'created': initial, 'identified': identified, 'confirmed': confirmed, 'retrieval': evidence}
            destination = folder / ('equipment-demo-mock.json' if args.mock_ocr else 'equipment-demo-real.json')
            destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            print(json.dumps({'session_id': initial['session_id'], 'ocr_mode': report['ocr_mode'],
                              'raw_ocr': identified['raw_ocr_text'], 'top_candidate': identified['ranked_candidates'][0],
                              'confirmation_status': confirmed['confirmation_status'], 'filters': confirmed['retrieval_filters'],
                              'retrieval_pages': [row['page_number'] for row in evidence['results']]}, indent=2, ensure_ascii=False))
            print(f'Demo saved: {destination}')
    finally:
        app.dependency_overrides.clear()


if __name__ == '__main__':
    main()
