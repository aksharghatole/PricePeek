import asyncio
import httpx
from pricepeek.shopping_search import parse,fetch,configured

def row(**kwargs):
    return {"title":"Example X100","source":"Example Store","price":"₹1,299.50","extracted_price":1299.5,"product_link":"https://example.com/p/1",**kwargs}

def test_parse():
    offers=parse({"shopping_results":[row(),row(price="$1,299.50"),row(price="₹500/month"),row(extracted_price=1),row(product_link="http://example.com"),row(installment={"price":99}),row(second_hand_condition="Used")]})
    assert len(offers)==1
    assert offers[0]["price_paise"]==129950
    assert offers[0]["data_method"]=="shopping_search"

def test_fetch(monkeypatch):
    monkeypatch.setenv("PRICEPEEK_SHOPPING_SEARCH_APPROVED","1")
    monkeypatch.setenv("SERPAPI_API_KEY","fake")
    assert configured()
    def handler(req):
        assert req.url.host=="serpapi.com"
        assert req.url.params["engine"]=="google_shopping"
        assert req.url.params["gl"]=="in"
        assert req.url.params["q"]=="Example X100"
        return httpx.Response(200,json={"shopping_results":[row()]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status,offers=await fetch(client,"Example X100")
            assert status=="retrieved" and len(offers)==1
    asyncio.run(run())

def test_not_configured(monkeypatch):
    monkeypatch.delenv("PRICEPEEK_SHOPPING_SEARCH_APPROVED",raising=False)
    monkeypatch.setenv("SERPAPI_API_KEY","fake")
    assert not configured()
