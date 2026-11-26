import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from time import monotonic
import httpx
from fastapi import FastAPI, Query, HTTPException
from . import flipkart, datayuge
from .limits import SearchLimits
from .sources import SOURCES, scan, UA
from .match import classify

app = FastAPI(title="PricePeek", version="0.4.0")
app.add_middleware(SearchLimits)
cache = OrderedDict()
provider_lock = asyncio.Lock()
provider_calls = 0
provider_day = None
provider_next = 0.0
cache_lock = asyncio.Lock()
semaphore = asyncio.Semaphore(3)
TTL = 900

@app.get("/health")
async def health():
    return {"status": "ok", "enabled_sources": sum(s.enabled or (s.name == 'Flipkart' and flipkart.configured()) for s in SOURCES) + int(datayuge.configured())}

@app.get("/")
async def root():
    return {"name":"PricePeek","status":"preview","docs":"/docs","health":"/health"}

async def provider_batch(client, query):
    global provider_calls, provider_day, provider_next
    result = {"source":"PriceYuge","status":"not_validated","search_url":"https://datayuge.com/products/price-comparison-api/","offers":[]}
    if not datayuge.configured():
        return result
    async with provider_lock:
        today = datetime.now(timezone.utc).date()
        if provider_day != today:
            provider_day, provider_calls = today, 0
        if provider_calls >= 80 or monotonic() < provider_next:
            return {**result,"status":"cooldown"}
        # Reserve two calls per search even if the second is not needed.
        provider_calls += 2
        try:
            status, offers = await datayuge.fetch(client,query)
        except (httpx.HTTPError, ValueError, TimeoutError):
            status, offers = "unavailable", []
        provider_next = monotonic() + (60 if status in ("rate_limited","authorization_required","unavailable") else 2)
        return {**result,"status":status,"offers":offers}

@app.get("/v1/search")
async def search(q: str = Query(min_length=2, max_length=120)):
    query = " ".join(q.split())
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Enter a product name or model")
    key = query.casefold()
    async with cache_lock:
        hit = cache.get(key)
        if hit and monotonic() - hit[0] < TTL:
            return {**hit[1], "cached": True}
    async with httpx.AsyncClient(timeout=5, headers={"User-Agent": UA}, trust_env=False) as client:
        batches = await asyncio.gather(*(scan(s, query, client, semaphore) for s in SOURCES))
        if datayuge.configured():
            batches.append(await provider_batch(client,query))
    offers = []
    seen = set()
    for batch in batches:
        for offer in batch.pop("offers"):
            match = classify(query, offer)
            source_name = offer.get("source",batch["source"])
            identity = (source_name, offer["url"], offer["name"], offer["price_paise"])
            if match != "different" and identity not in seen:
                seen.add(identity)
                offers.append({**offer, "source": source_name, "match": match})
    offers.sort(key=lambda x: (x["match"] != "identifier_match", x["price_paise"]))
    result = {"query": query, "checked_at": datetime.now(timezone.utc).isoformat(),
              "cached": False, "offers": offers, "sources": batches,
              "notice": "Candidate offers may differ in variant. Provider snapshots can be a day old or more; retrieval time is not the merchant price timestamp. Shipping, location and checkout discounts are not verified."}
    # Do not retain transient failures or empty results for 15 minutes.
    if not offers or any(b["status"] in {"busy","cooldown","unavailable","rate_limited","authorization_required"} for b in batches):
        return result
    async with cache_lock:
        cache[key] = (monotonic(), result)
        cache.move_to_end(key)
        while len(cache) > 128:
            cache.popitem(last=False)
    return result
