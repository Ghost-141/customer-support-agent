from tools.qa import _build_disambiguation


def test_build_disambiguation_returns_payload_for_multiple_titles():
    products = [
        {"id": 1, "title": "Kiwi Fruit", "brand": "FreshCo", "category": "groceries"},
        {"id": 2, "title": "Kiwi Shoe Polish", "brand": "Kiwi", "category": "beauty"},
    ]

    result = _build_disambiguation("kiwi", products)

    assert result is not None
    assert result["type"] == "product_disambiguation"
    assert len(result["items"]) == 2


def test_build_disambiguation_ignores_duplicate_titles():
    products = [
        {"id": 1, "title": "Essence Mascara Lash Princess"},
        {"id": 2, "title": "Essence Mascara Lash Princess"},
    ]

    result = _build_disambiguation("essence mascara", products)
    assert result is None
