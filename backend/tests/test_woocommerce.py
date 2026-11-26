import asyncio
import json
import httpx
import pytest
from pricepeek.woocommerce import Store, stores, parse, fetch

STORE=Store("Example","https://example.com")
ROW={"id":42,"name":"Example X100","type":"simple","permalink":"https://example.com/product/x100/","prices":{"price":"129950","currency_code":"INR","currency_minor_unit":2,"price_range":None},"is_in_stock":True}

def test_parse():
    result=parse([ROW,{**ROW,"type":"variable"},{**ROW,"permalink":"https://evil.example.com/p"},{**ROW,"is_password_protected":True},{**ROW,"prices":{**ROW["prices"],"currency_code":"USD"}}],STORE)
    assert len(result)==1
    assert result[0]["price_paise"]==129950
    assert result[0]["availability"]=="InStock"

def test_config(monkeypatch):
    monkeypatch.setenv("PRICEPEEK_APPROVED_WOO_STORES",json.dumps([{"name":"Example","origin":"https://example.com","approved":True},{"name":"Not approved","origin":"https://example.org"}]))
    assert stores()==(STORE,)
    for origin in ("http://example.com","https://127.0.0.1","https://example.com/private","https://u@example.com","https://example.local"):
        monkeypatch.setenv("PRICEPEEK_APPROVED_WOO_STORES",json.dumps([{"name":"Bad","origin":origin,"approved":True}]))
        with pytest.raises(ValueError):
            stores()

def test_fetch():
    def handler(req):
        assert req.url.path=="/wp-json/wc/store/v1/products"
        assert req.url.params["search"]=="X100"
        return httpx.Response(200,json=[ROW])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status,offers=await fetch(client,STORE,"X100")
            assert status=="retrieved" and len(offers)==1
    asyncio.run(run())
