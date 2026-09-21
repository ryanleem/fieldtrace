"""Prototype qualitative visual-inspection evaluation; uses the configured live API.

Expected labels, source filenames/descriptions and annotation notes are never sent
to the model. This is a small qualitative review, not a statistical CV benchmark.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import get_settings
from app.services.inspection_images import run_vision, validate_image
from app.services.vision_provider import get_vision_provider, configured_vision_model, VisionImage, VISION_PROMPT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/evaluation/manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/evaluation/results.json')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    settings = get_settings()
    provider = get_vision_provider()
    report = dict(title='prototype qualitative visual-inspection evaluation',
                  created_at=datetime.now(timezone.utc).isoformat(), provider=settings.vision_provider,
                  model=configured_vision_model(settings),
                  prompt=VISION_PROMPT, results=[],
                  interpretation='Small qualitative sample, not field accuracy. Scope guard is lexical; visual and semantic review is still required.')
    for entry in manifest['images']:
        path = (args.manifest.parent / 'images' / entry['filename']).resolve()
        if not path.is_relative_to((args.manifest.parent / 'images').resolve()):
            raise ValueError('Manifest image escapes evaluation folder')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Image checksum mismatch: {entry["filename"]}')
        mime, _ = validate_image(data, settings)
        result, raw, error = run_vision(provider, VisionImage(data, mime), {'view_label': entry['view_label']})
        row = dict(filename=entry['filename'], view_label=entry.get('view_label'),
                   expected_issue_types=entry.get('expected_issue_types'),
                   expectation=entry.get('annotation'),
                   provider=settings.vision_provider, model=configured_vision_model(settings),
                   analysis=result.model_dump() if result else None, raw_attempts=raw, error=error,
                   structured_output_valid=result is not None,
                   observation_scope_guard_passed=result is not None,
                   human_review_required=True,
                   returned_issue_types=[f.issue_type for f in result.findings] if result else [])
        report['results'].append(row)
        print(json.dumps({k: v for k, v in row.items() if k != 'raw_attempts'}, ensure_ascii=True), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 1 if any(r['error'] for r in report['results']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
