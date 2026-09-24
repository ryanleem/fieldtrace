import json

from fastapi.testclient import TestClient
import pytest

from app.config import get_settings
from app.main import app


@pytest.mark.corpus
def test_api_ingestion_and_evidence_only_search(monkeypatch):
    from app.auth import require_user
    from uuid import uuid4
    monkeypatch.setitem(app.dependency_overrides, require_user, lambda: uuid4())
    entry = json.loads((get_settings().manuals_dir / "manifest.json").read_text(encoding="utf-8"))[0]
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["pgvector_version"]
        ingest = client.post("/documents/ingest", json=entry)
        assert ingest.status_code == 200 and ingest.json()["duplicate"] is True
        response = client.post("/search", json={"query": "A4F6", "equipment_model": "ACS880", "top_k": 5})
        assert response.status_code == 200
        data = response.json()
        assert set(data) == {"query", "results"}
        assert len(data["results"]) == 5
        assert all(item["document_id"] and item["page_number"] >= 1 for item in data["results"])
        assert client.post("/search", json={"query": "   "}).status_code == 422
        assert client.post("/search", json={"query": "A4F6", "top_k": 0}).status_code == 422
        assert client.post("/documents/ingest", json={"filename": "../escape.pdf", "title": "Bad path"}).status_code == 422
