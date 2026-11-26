import asyncio
import json
import httpx
from pricepeek.crowcrowcrow import parse, fetch

ROW={"title":"Example protein bar","brand":"Example","url":"https://crowcrowcrow.com/p/protein-bar/SKU1","sku":"SKU1","price":{"currency":"INR","price":299.5},"inStock":True}

def test_parse():
    rows=[ROW,{**ROW,"price":{"currency":"USD","price":299.5}},{**ROW,"url":"https://crowcrowcrow.com.evil.invalid/p/1"},{**ROW,"price":{"currency":"INR","price":"NaN"}}]
    result=parse({"content":[{"type":"text","text":json.dumps({"products":rows})}]})
    assert len(result)==1
    assert result[0]["price_paise"]==29950
    assert result[0]["data_method"]=="retailer_mcp"
    assert parse({"structuredContent":{"items":[ROW]}})[0]["availability"]=="InStock"

def test_session(monkeypatch):
    monkeypatch.delenv("PRICEPEEK_CCC_DISABLED",raising=False)
    calls=[]
    def handler(req):
        assert req.url.host=="crowcrowcrow.com"
        if req.method=="DELETE":
            assert req.headers["Mcp-Session-Id"]=="test-session"
            return httpx.Response(204)
        payload=json.loads(req.content)
        calls.append(payload["method"])
        if payload["method"]=="initialize":
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26"}},headers={"Mcp-Session-Id":"test-session"})
        assert req.headers["Mcp-Session-Id"]=="test-session"
        if payload["method"]=="notifications/initialized":
            return httpx.Response(202)
        assert payload["params"]["name"]=="products.search"
        assert payload["params"]["arguments"]=={"query":"protein bar","limit":5}
        data={"jsonrpc":"2.0","id":2,"result":{"structuredContent":{"products":[ROW]}}}
        return httpx.Response(200,text="event: message\ndata: "+json.dumps(data)+"\n\n",headers={"Content-Type":"text/event-stream"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status,offers=await fetch(client,"protein bar")
            assert status=="retrieved" and len(offers)==1
    asyncio.run(run())
    assert calls==["initialize","notifications/initialized","tools/call"]
