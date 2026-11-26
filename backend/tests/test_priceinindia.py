import asyncio
import json
from datetime import datetime, timezone
import httpx
from pricepeek.priceinindia import parse,fetch,configured,retry_delay

ROW={"title":"Sony WH-1000XM5","brand":"Sony","store":"amazon.in","price":24999.50,"currency":"INR","productUrl":"https://www.priceinindia.website/go/abc","productPageUrl":"https://www.priceinindia.website/products/abc","lastUpdated":int(datetime.now(timezone.utc).timestamp()),"outOfStock":False}

def test_parse():
    items=parse({"structuredContent":{"products":[ROW,{**ROW,"currency":"USD"},{**ROW,"productUrl":"https://evil.invalid/p"},{**ROW,"lastUpdated":None},{**ROW,"price":"NaN"}]}})
    assert len(items)==1
    assert items[0]["price_paise"]==2499950
    assert items[0]["url"]==ROW["productUrl"]
    assert items[0]["citation_url"]==ROW["productPageUrl"]
    assert items[0]["data_method"]=="priceinindia_snapshot"

def test_default_disabled(monkeypatch):
    monkeypatch.delenv("PRICEPEEK_PRICEININDIA_APPROVED",raising=False)
    assert not configured()
    assert retry_delay("120")==120

def test_rpc():
    def handler(req):
        assert req.url.host=="mcp.priceinindia.website"
        p=json.loads(req.content)
        if p["method"]=="initialize":
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26"}})
        if p["method"]=="notifications/initialized":
            return httpx.Response(202)
        assert p["params"]["name"]=="search_products"
        assert p["params"]["arguments"]["query"]=="Sony WH-1000XM5"
        return httpx.Response(200,json={"jsonrpc":"2.0","id":2,"result":{"structuredContent":{"products":[ROW]}}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status,offers,delay=await fetch(client,"Sony WH-1000XM5")
            assert status=="retrieved" and len(offers)==1 and delay==10
    asyncio.run(run())
