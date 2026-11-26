"""Opt-in PriceYuge comparison API; provider observations are not live quotes."""
import asyncio
import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from .match import classify
import httpx

BASE = "https://price-api.datayuge.com/api/v1/compare/"
MAX_BODY = 1_500_000
# Known retailer hosts only; provider affiliate links stay intact.
HOSTS = {
    "amazon": {"www.amazon.in","amazon.in"},
    "flipkart": {"www.flipkart.com","flipkart.com","dl.flipkart.com"},
    "croma": {"www.croma.com","croma.com"},
    "reliancedigital": {"www.reliancedigital.in","reliancedigital.in"},
    "vijaysales": {"www.vijaysales.com","vijaysales.com"},
    "tatacliq": {"www.tatacliq.com","tatacliq.com"},
    "snapdeal": {"www.snapdeal.com","snapdeal.com"},
    "shopclues": {"www.shopclues.com","shopclues.com"},
}
def configured():
    return os.getenv("PRICEPEEK_DATAYUGE_APPROVED") == "1" and bool(os.getenv("DATAYUGE_API_KEY"))

def link_ok(url, store):
    if not isinstance(url,str):
        return False
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.port not in (None,443):
            return False
        return p.hostname in HOSTS.get(store,set()) or (p.hostname == "price-api.datayuge.com" and p.path == "/redirect")
    except ValueError:
        return False

def parse_detail(payload, query):
    data = payload.get("data") if isinstance(payload,dict) else None
    if not isinstance(data,dict) or data.get("is_comparable") is not True:
        return []
    title = data.get("product_name")
    if not isinstance(title,str) or not title.strip():
        return []
    brand = str(data.get("product_brand") or "")[:100]
    model = str(data.get("product_model") or "")[:100]
    if classify(query,{"name":title,"brand":brand,"model":model}) == "different":
        return []
    offers = []
    stores = data.get("stores")
    if not isinstance(stores,list):
        return []
    for group in stores[:30]:
        if not isinstance(group,dict):
            continue
        for store, p in group.items():
            if store not in HOSTS or not isinstance(p,dict):
                continue
            url = p.get("product_store_url")
            if not link_ok(url,store):
                continue
            try:
                price = Decimal(str(p.get("product_price")))
                if not price.is_finite() or not 0 < price <= 100000000 or price != price.quantize(Decimal("0.01")):
                    continue
            except (InvalidOperation, ValueError):
                continue
            name = str(p.get("product_store") or store)[:100]
            offers.append({"name":title[:300],"brand":brand,"model":model,"gtin":"",
                           "price_paise":int(price*100),"currency":"INR","url":url,
                           "availability":"unknown","condition":"unknown",
                           "source":name,"data_method":"provider_snapshot",
                           "variant":str(p.get("product_color") or "")[:100]})
    return offers

async def request(client, action, params):
    # Fixed API endpoints; never fetch a URL supplied by a third party.
    async with client.stream("GET", BASE+action, params={**params,"api_key":os.environ["DATAYUGE_API_KEY"]},follow_redirects=False) as response:
        if response.status_code == 429:
            return "rate_limited", None
        if response.status_code in (401,403):
            return "authorization_required", None
        response.raise_for_status()
        body=bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body)>MAX_BODY:
                raise ValueError("response too large")
    return "ok",json.loads(body)

async def fetch(client, query):
    if not configured():
        return "not_validated",[]
    async with asyncio.timeout(15):
        status, payload = await request(client,"search",{"product":query,"page":1})
        if status != "ok":
            return status,[]
        products = payload.get("data") if isinstance(payload,dict) else None
        if not isinstance(products,list):
            raise ValueError("unexpected search response")
        # Maximum two provider calls per uncached search; only a plausible comparable match.
        selected = None
        for p in products[:20]:
            if not isinstance(p,dict) or p.get("can_compare") is not True:
                continue
            ident = p.get("product_id")
            title = p.get("product_title")
            if isinstance(ident,str) and re.fullmatch(r"[A-Za-z0-9_=-]{1,120}",ident) and isinstance(title,str) and classify(query,{"name":title})!="different":
                selected=ident
                break
        if not selected:
            return "no_offers",[]
        status, payload = await request(client,"detail",{"id":selected})
        if status != "ok":
            return status,[]
        offers = parse_detail(payload,query)
        return ("retrieved" if offers else "no_offers"), offers
