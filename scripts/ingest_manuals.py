import json
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.db.init_db import initialize
from app.db.session import get_engine
from app.schemas.document import IngestRequest
from app.services.embeddings import get_embedder
from app.services.ingestion import ingest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Atomically re-extract/re-embed each manifest PDF; rollback preserves prior version on failure")
    args = parser.parse_args()
    settings = get_settings()
    engine, embedder = get_engine(), get_embedder()
    initialize(engine, embedder)
    reports = []
    for entry in json.loads((settings.manuals_dir / "manifest.json").read_text(encoding="utf-8")):
        print(f"Ingesting {entry['filename']}...", flush=True)
        result = ingest(engine, IngestRequest(**entry), embedder, replace=args.rebuild)
        reports.append({"filename": entry["filename"], **result.model_dump(mode="json")})
        print(json.dumps({key: value for key, value in reports[-1].items() if key != "warnings"}, indent=2), flush=True)
        print(f"Pages with extraction warnings: {len(result.warnings)}", flush=True)
    (settings.processed_dir / "ingestion-summary.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
