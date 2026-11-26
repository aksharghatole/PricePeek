import json
from fastapi.testclient import TestClient
from pricepeek.api import app
from pricepeek.extract import extract
from pricepeek.match import classify

def sample(**changes):
    product = {"@type":"Product", "name":"Logitech G304", "brand":{"name":"Logitech"},
               "offers":{"@type":"Offer","price":"2499.50","priceCurrency":"INR","url":"/p/123"}}
    product["offers"].update(changes)
    return '<script type="application/ld+json">'+json.dumps(product)+'</script>'

def test_extract():
    offer = extract(sample(), "https://example.com/search")[0]
    assert offer["price_paise"] == 249950
    assert offer["url"] == "https://example.com/p/123"
    assert classify("Logitech G304", offer) == "candidate"

def test_reject_invalid_prices_and_links():
    for changes in ({"price":"NaN"}, {"price":"-1"}, {"priceCurrency":"USD"}, {"url":"https://evil.example/p"}, {"@type":"AggregateOffer"}):
        assert extract(sample(**changes), "https://example.com/search") == []

def test_matching():
    assert classify("Galaxy S25 256GB", {"name":"Galaxy S25 128GB"}) == "different"
    assert classify("Logitech G304", {"name":"Logitech G304 case"}) == "different"
    assert classify("Logitech G304", {"name":"Logitech G304", "condition":"RefurbishedCondition"}) == "different"
    assert classify("4006381333931", {"name":"Item","gtin":"4006381333931"}) == "identifier_match"

def test_disabled_sources_never_invent_prices(monkeypatch):
    from pricepeek import crowcrowcrow
    monkeypatch.setenv('PRICEPEEK_CCC_DISABLED','1')
    with TestClient(app) as client:
        r = client.get("/v1/search", params={"q":"Logitech G304"})
        assert r.status_code == 200
        data = r.json()
        assert data["offers"] == []
        assert all(s["status"] == "not_validated" for s in data["sources"])
        assert client.get("/health").json()["enabled_sources"] == 0
