import asyncio
import httpx
from pricepeek.flipkart import parse, fetch, configured

def payload(**changes):
    data = {"title":"Example mouse X100","productBrand":"Example",
            "productUrl":"http://dl.flipkart.com/dl/mouse/p/abc?affid=example",
            "flipkartSellingPrice":{"amount":"1299.50","currency":"INR"},
            "flipkartSpecialPrice":{"amount":99,"currency":"INR"},
            "productId":"MOUSE123","inStock":True}
    data.update(changes)
    return {"productInfoList":[{"productBaseInfoV1":data}]}

def test_parse():
    offer = parse(payload())[0]
    assert offer["price_paise"] == 129950
    assert offer["availability"] == "InStock"
    assert offer["url"].startswith("https://dl.flipkart.com/")
    assert offer["data_method"] == "affiliate_api"

def test_invalid():
    for changes in ({"productUrl":"https://flipkart.com.evil.invalid/a"},
                    {"flipkartSellingPrice":{"amount":"NaN","currency":"INR"}},
                    {"flipkartSellingPrice":{"amount":123,"currency":"USD"}},
                    {"flipkartSellingPrice":None}):
        assert parse(payload(**changes)) == []

def test_mock_transport(monkeypatch):
    monkeypatch.setenv("PRICEPEEK_FLIPKART_APPROVED","1")
    monkeypatch.setenv("FLIPKART_AFFILIATE_ID","test")
    monkeypatch.setenv("FLIPKART_AFFILIATE_TOKEN","fake")
    assert configured()
    def handler(request):
        assert request.url.host == "affiliate-api.flipkart.net"
        assert request.url.params["query"] == "mouse X100"
        assert request.headers["Fk-Affiliate-Token"] == "fake"
        return httpx.Response(200,json=payload())
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status, offers = await fetch(client,"mouse X100")
            assert status == "retrieved"
            assert len(offers) == 1
    asyncio.run(run())

def test_requires_explicit_approval(monkeypatch):
    monkeypatch.delenv("PRICEPEEK_FLIPKART_APPROVED",raising=False)
    monkeypatch.setenv("FLIPKART_AFFILIATE_ID","test")
    monkeypatch.setenv("FLIPKART_AFFILIATE_TOKEN","fake")
    assert not configured()
