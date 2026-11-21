from app.retrieval.text import or_tsquery, query_terms, tsquery_terms


def test_the_query_terms_are_the_distinct_words_the_or_query_joins() -> None:
    question = "When did Ismail Khatri settle in Bagh, and did Ismail stay?"
    assert query_terms(question) == ["when", "did", "ismail", "khatri", "settle", "bagh", "and", "stay"]
    assert or_tsquery(question) == "when | did | ismail | khatri | settle | bagh | and | stay"


def test_an_or_query_splits_back_into_its_terms_once_each() -> None:
    assert tsquery_terms("alum | madder | alum") == ["alum", "madder"]
    assert tsquery_terms("alum") == ["alum"]
    assert tsquery_terms(" | ") == []
