from app.schemas.search import SearchRequest
from app.services.query_normalization import retrieval_query


def test_cleanup_preserves_symptoms_negation_and_technical_identifiers():
    q = SearchRequest(query="An ABB motor is overheating. What should I inspect?")
    assert retrieval_query(q) == "motor overheating inspect"
    assert retrieval_query(q.model_copy(update={"equipment_family": "Induction Motors and Generators"})) == "overheating inspect"
    assert retrieval_query(SearchRequest(query="ACS880 is not running at 400 V X13", equipment_model="ACS880")) == "not running at 400 V X13"
    assert retrieval_query(SearchRequest(query="A4F6")) == "A4F6"
    assert retrieval_query(SearchRequest(query="ABB")) == "ABB"
