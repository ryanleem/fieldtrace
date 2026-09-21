from uuid import UUID

import pytest

from app.schemas.search import Evidence
from app.services.hybrid_search import reciprocal_rank_fusion


def evidence(number, semantic=None, keyword=None):
    return Evidence(rank=1, chunk_id=UUID(int=number), document_id=UUID(int=99), document_title="Test fixture",
                    source_url=None, citation_url=None, document_number=None, revision=None,
                    equipment_model=None, equipment_family=None, page_number=1, printed_page_label=None,
                    section_title=None, content_type="paragraph", chunk_index=number, chunk_text="placeholder",
                    source_blocks=[], safety_context=[], extraction_notes=[],
                    semantic_score=semantic, keyword_score=keyword)


def test_exact_rrf_order_and_values():
    a, b, c = evidence(1, 0.9), evidence(2, 0.5), evidence(3, keyword=5000)
    result = reciprocal_rank_fusion([a, b], [b.model_copy(update={"keyword_score": 4}), c], k=60)
    assert [r.chunk_id.int for r in result] == [2, 1, 3]
    assert result[0].rrf_score == pytest.approx(1/62 + 1/61)
    assert result[0].semantic_rank == 2 and result[0].keyword_rank == 1
    assert result[1].rrf_score == pytest.approx(1/61)
    assert result[2].rrf_score == pytest.approx(1/62)
    assert b.keyword_rank is None  # Inputs are not mutated.


def test_empty_ties_duplicates_and_top_k():
    assert reciprocal_rank_fusion([], []) == []
    result = reciprocal_rank_fusion([evidence(2), evidence(2)], [evidence(1)], top_k=1)
    assert result[0].chunk_id.int == 1  # Stable UUID tie-break; duplicate does not add score.
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], [], k=0)
