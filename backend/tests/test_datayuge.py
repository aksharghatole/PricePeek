import asyncio
import httpx
from pricepeek.datayuge import parse_detail, fetch

def detail():
    return {"data":{"product_name":"Example X100","product_model":"X100","product_brand":"Example","is_comparable":True,"stores":[
        {"amazon":{"product_store":"Amazon.in","product_store_url":"https://price-api.datayuge.com/redirect?id=abc","product_price":"1499.99"}},
        {"croma":{"product_store":"Croma","product_store_url":"https://www.croma.com/p/1","product_price":"1599"}},
        {"flipkart":{"product_store_url":"https://evil.invalid/p","product_price":"1"}},
        {"snapdeal":[]}
    ]}}

def test_parse_detail():
    offers=parse_detail(detail(),"Example X100")
    assert [x["price_paise"] for x in offers]==[149999,159900]
    assert all(x["data_method"]=="provider_snapshot" for x in offers)
    assert parse_detail(detail(),"Example X200")==[]

def test_fetch(monkeypatch):
    monkeypatch.setenv("PRICEPEEK_DATAYUGE_APPROVED","1")
    monkeypatch.setenv("DATAYUGE_API_KEY","fake")
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        assert req.url.host=="price-api.datayuge.com"
        assert req.url.params["api_key"]=="fake"
        if req.url.path.endswith("/search"):
            return httpx.Response(200,json={"data":[{"product_title":"Example X100","product_id":"test123","can_compare":True}]})
        return httpx.Response(200,json=detail())
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status,offers=await fetch(client,"Example X100")
            assert status=="retrieved" and len(offers)==2
    asyncio.run(run())
    assert len(calls)==2
