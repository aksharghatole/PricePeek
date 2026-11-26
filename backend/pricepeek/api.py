import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from time import monotonic
import httpx
from fastapi import FastAPI, Query, HTTPException
from . import flipkart, datayuge, openprices, shopping_search, crowcrowcrow, woocommerce
from .limits import SearchLimits
from .sources import SOURCES, scan, UA
from .match import classify
from .comparison import assign_groups

app = FastAPI(title="PricePeek", version="0.10.0")
app.add_middleware(SearchLimits)
cache = OrderedDict()
provider_lock = asyncio.Lock()
provider_calls = 0
provider_day = None
provider_next = 0.0
shopping_lock = asyncio.Lock()
shopping_next = 0.0
shopping_month = None
shopping_calls = 0
ccc_lock = asyncio.Lock()
ccc_next = 0.0
woo_stores = woocommerce.stores()
woo_locks = {s.origin:asyncio.Lock() for s in woo_stores}
woo_next = {}
cache_lock = asyncio.Lock()
semaphore = asyncio.Semaphore(3)
TTL = 900

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version, "enabled_sources": sum(s.enabled or (s.name == 'Flipkart' and flipkart.configured()) for s in SOURCES) + int(datayuge.configured()) + int(shopping_search.configured()) + int(crowcrowcrow.configured()) + len(woo_stores)}

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

async def shopping_batch(client,query):
    global shopping_next, shopping_month, shopping_calls
    from urllib.parse import quote_plus
    result={"source":"Shopping web search","search_url":"https://www.google.com/search?tbm=shop&q="+quote_plus(query),"status":"not_validated","offers":[]}
    if not shopping_search.configured():
        return result
    if shopping_lock.locked():
        return {**result,"status":"busy"}
    async with shopping_lock:
        month=datetime.now(timezone.utc).strftime("%Y-%m")
        if shopping_month!=month:
            shopping_month,shopping_calls=month,0
        if shopping_calls>=200 or monotonic()<shopping_next:
            return {**result,"status":"cooldown"}
        shopping_calls+=1
        try:
            status,offers=await shopping_search.fetch(client,query)
        except (httpx.HTTPError,ValueError,TimeoutError):
            status,offers="unavailable",[]
        shopping_next=monotonic()+(60 if status in ("rate_limited","authorization_required","unavailable") else 2)
        return {**result,"status":status,"offers":offers}

async def ccc_batch(client,query):
    global ccc_next
    result={"source":"CrowCrowCrow","search_url":"https://crowcrowcrow.com/","status":"not_validated","offers":[]}
    if not crowcrowcrow.configured():
        return result
    if ccc_lock.locked():
        return {**result,"status":"busy"}
    async with ccc_lock:
        if monotonic()<ccc_next:
            return {**result,"status":"cooldown"}
        try:
            status,offers=await crowcrowcrow.fetch(client,query)
        except (httpx.HTTPError,ValueError,TimeoutError):
            status,offers="unavailable",[]
        # At most four HTTP messages per search, at least 8 seconds between searches.
        ccc_next=monotonic()+(60 if status in ("rate_limited","authorization_required","unavailable") else 8)
        return {**result,"status":status,"offers":offers}

async def woo_batch(client,store,query):
    result={"source":store.name,"search_url":woocommerce.search_url(store,query),"status":"not_validated","offers":[]}
    lock=woo_locks[store.origin]
    if lock.locked():
        return {**result,"status":"busy"}
    async with lock:
        if monotonic()<woo_next.get(store.origin,0):
            return {**result,"status":"cooldown"}
        try:
            async with semaphore:
                status,offers=await woocommerce.fetch(client,store,query)
        except (httpx.HTTPError,ValueError,TimeoutError):
            status,offers="unavailable",[]
        woo_next[store.origin]=monotonic()+(60 if status in ("rate_limited","authorization_required","unavailable") else 5)
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
        tasks = [scan(s,query,client,semaphore) for s in SOURCES]
        tasks.extend(woo_batch(client,s,query) for s in woo_stores)
        if crowcrowcrow.configured():
            tasks.append(ccc_batch(client,query))
        if datayuge.configured():
            tasks.append(provider_batch(client,query))
        if shopping_search.configured():
            tasks.append(shopping_batch(client,query))
        batches = await asyncio.gather(*tasks)
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
    comparison_count = assign_groups(offers)
    offers.sort(key=lambda x: (not bool(x.get("comparison_group")), x.get("comparison_group",""), x["price_paise"]))
    result = {"query": query, "checked_at": datetime.now(timezone.utc).isoformat(),
              "cached": False, "offers": offers, "sources": batches, "comparison_group_count": comparison_count,
              "notice": "Candidate offers may differ in variant. Shopping search prices are unverified listings. Provider snapshots can be a day old or more; retrieval time is not the merchant price timestamp. Compare exact variants and pack quantities, not just prices. Shipping, location and checkout discounts are not verified."}
    # Do not retain transient failures or empty results for 15 minutes.
    if not offers or any(b["status"] in {"busy","cooldown","unavailable","rate_limited","authorization_required"} for b in batches):
        return result
    async with cache_lock:
        cache[key] = (monotonic(), result)
        cache.move_to_end(key)
        while len(cache) > 128:
            cache.popitem(last=False)
    return result

# Separate endpoint to avoid mixing ODbL observations and proprietary retail offers.
open_lock = asyncio.Lock()
open_next = 0.0

@app.get("/v1/observations")
async def observations(barcode: str = Query(min_length=8,max_length=14)):
    global open_next
    if not openprices.valid_barcode(barcode):
        raise HTTPException(422, "Invalid GTIN check digit or length")
    async with open_lock:
        if monotonic() < open_next:
            raise HTTPException(429, "Please retry in a few seconds")
        open_next=monotonic()+5
        try:
            async with asyncio.timeout(12):
                async with httpx.AsyncClient(timeout=8,headers={"User-Agent":UA},trust_env=False) as client:
                    items=await openprices.fetch(client,barcode)
        except (httpx.HTTPError,ValueError,TimeoutError):
            raise HTTPException(503,"Open Prices temporarily unavailable")
    return {"barcode":barcode,"observations":items,"attribution":openprices.ATTRIBUTION,
            "license":"https://opendatacommons.org/licenses/odbl/1-0/",
            "notice":"Historical community observations in INR, not current offers or checkout prices. Coverage may be sparse."}
