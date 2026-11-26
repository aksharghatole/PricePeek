import asyncio
import json
import httpx
from pricepeek.sources import Source, web_scan, configured_sources

def fixture():
    product = {"@type":"Product","name":"Example X100","offers":{"@type":"Offer","priceCurrency":"INR","price":"1999","url":"/products/x100"}}
    return '<script type="application/ld+json">'+json.dumps(product)+'</script>'

def test_web_flow():
    calls = []
    delays = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200,text="User-agent: PricePeek\nDisallow: /products/private\nCrawl-delay: 3")
        if request.url.path == "/search":
            return httpx.Response(200,text='<a href="/products/x100">a</a><a href="/products/private">b</a><a href="/products-other/x">c</a><a href="https://elsewhere.invalid/products/x">d</a>')
        return httpx.Response(200,text=fixture())
    async def pause(seconds):
        delays.append(seconds)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status, offers, delay = await web_scan(Source("Test","https://example.com/search?q={query}",True,"/products"),"Example X100",client,pause)
            assert status == "retrieved"
            assert offers[0]["price_paise"] == 199900
            assert offers[0]["data_method"] == "public_web"
            assert delay == 3
    asyncio.run(run())
    assert calls == ["/robots.txt","/search","/products/x100"]
    assert delays == [3,3]

def test_disallow_search():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200,text="User-agent: *\nDisallow: /search")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            status, offers, _ = await web_scan(Source("Test","https://example.com/search?q={query}",True),"abc",client,asyncio.sleep)
            assert status == "disallowed" and offers == []
    asyncio.run(run())
    assert calls == ["/robots.txt"]

def test_approval_config(monkeypatch):
    monkeypatch.setenv("PRICEPEEK_WEB_CROMA_APPROVED","1")
    monkeypatch.setenv("PRICEPEEK_WEB_CROMA_PRODUCT_PREFIX","/products")
    source = next(s for s in configured_sources() if s.slug=="croma")
    assert source.enabled and source.product_path_prefix == "/products"
    assert source.search_url("a & b").endswith("a+%26+b")
