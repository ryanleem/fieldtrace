"""Inspectable retrieval output, including poor/empty results; no answer generation."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.db.session import get_engine
from app.schemas.search import SearchRequest
from app.services.embeddings import get_embedder
from app.services.hybrid_search import search_all
from app.services.query_normalization import retrieval_query


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/retrieval-results.json")
    arguments = parser.parse_args()
    queries = json.loads((ROOT / "data/evaluation_queries.json").read_text(encoding="utf-8"))
    engine, embedder = get_engine(), get_embedder()
    report = []
    for case in queries:
        request = SearchRequest(**case["request"])
        modes = search_all(engine, request, embedder)
        print(f"\nQUERY: {request.query}")
        print(f"RETRIEVAL QUERY: {retrieval_query(request)}")
        for mode, results in modes.items():
            print(f"\n{mode.upper()} TOP 5 ({len(results)} candidates)")
            for item in results[:5]:
                print(f"{item.rank}. {item.document_title} | physical PDF p.{item.page_number} | {item.section_title}")
                print(f"  semantic={item.semantic_rank} keyword={item.keyword_rank} RRF={item.rrf_score}")
                print("  " + item.chunk_text[:300].replace("\n", " "))
        report.append({"request": request.model_dump(mode="json"), "retrieval_query": retrieval_query(request),
                       "results": {mode: [item.model_dump(mode="json") for item in rows[:5]] for mode, rows in modes.items()}})
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull evidence saved to {arguments.output}")


if __name__ == "__main__":
    main()
