import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from time import monotonic
import httpx
from fastapi import FastAPI, Query, HTTPException
from . import flipkart
from .sources import SOURCES, scan, UA
from .match import classify

app = FastAPI(title="PricePeek", version="0.2.0")
cache = OrderedDict()
cache_lock = asyncio.Lock()
semaphore = asyncio.Semaphore(3)
TTL = 900

@app.get("/health")
async def health():
    return {"status": "ok", "enabled_sources": sum(s.enabled or (s.name == 'Flipkart' and flipkart.configured()) for s in SOURCES)}

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
    offers = []
    seen = set()
    for batch in batches:
        for offer in batch.pop("offers"):
            match = classify(query, offer)
            identity = (batch["source"], offer["url"], offer["name"], offer["price_paise"])
            if match != "different" and identity not in seen:
                seen.add(identity)
                offers.append({**offer, "source": batch["source"], "match": match})
    offers.sort(key=lambda x: (x["match"] != "identifier_match", x["price_paise"]))
    result = {"query": query, "checked_at": datetime.now(timezone.utc).isoformat(),
              "cached": False, "offers": offers, "sources": batches,
              "notice": "Candidate offers may differ in variant. Shipping, location and checkout discounts are not verified."}
    # Do not retain transient failures or empty results for 15 minutes.
    if not offers:
        return result
    async with cache_lock:
        cache[key] = (monotonic(), result)
        cache.move_to_end(key)
        while len(cache) > 128:
            cache.popitem(last=False)
    return result
