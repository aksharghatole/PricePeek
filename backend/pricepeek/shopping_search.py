"""Optional India shopping-search provider. Prices are unverified search listings."""
import asyncio
import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import httpx

ENDPOINT = "https://serpapi.com/search.json"
MAX_BYTES = 2_000_000

def configured():
    return os.getenv("PRICEPEEK_SHOPPING_SEARCH_APPROVED") == "1" and bool(os.getenv("SERPAPI_API_KEY"))

def parse(payload):
    if not isinstance(payload,dict) or payload.get("error"):
        raise ValueError("provider error")
    rows = payload.get("shopping_results",[])
    if not isinstance(rows,list):
        raise ValueError("unexpected results")
    offers=[]
    for row in rows[:50]:
        if not isinstance(row,dict):
            continue
        title, seller, raw = row.get("title"),row.get("source"),row.get("price")
        url=row.get("product_link") or row.get("link")
        if not all(isinstance(v,str) and v.strip() for v in (title,seller,raw,url)):
            continue
        # Require explicit INR and one plain price, not EMI, range or estimate.
        m=re.fullmatch(r"(?:₹|INR\s*|Rs\.?\s*)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",raw.strip(),re.I)
        if not m or row.get("installment") or row.get("second_hand_condition"):
            continue
        try:
            amount=Decimal(m.group(1).replace(",",""))
            numeric=Decimal(str(row.get("extracted_price",amount)))
            if not amount.is_finite() or amount!=numeric or not 0<amount<=100000000:
                continue
            link=urlsplit(url)
            if link.scheme!="https" or not link.hostname or link.username or link.password or link.port not in (None,443):
                continue
            # Search-result links are navigation only, never server-fetched.
            if link.hostname in ("localhost","serpapi.com","www.serpapi.com") or "." not in link.hostname:
                continue
        except (InvalidOperation,ValueError):
            continue
        offers.append({"name":title[:300],"source":seller[:100],"brand":"","model":"","gtin":"",
                       "price_paise":int(amount*100),"currency":"INR","url":url,
                       "condition":"unknown","availability":"unknown",
                       "data_method":"shopping_search","variant":""})
    return offers

async def fetch(client,query):
    if not configured():
        return "not_validated",[]
    async with asyncio.timeout(20):
        async with client.stream("GET",ENDPOINT,params={"engine":"google_shopping","q":query,"gl":"in","hl":"en","google_domain":"google.co.in","api_key":os.environ["SERPAPI_API_KEY"]},follow_redirects=False,timeout=15) as response:
            if response.status_code==429:
                return "rate_limited",[]
            if response.status_code in (401,403):
                return "authorization_required",[]
            response.raise_for_status()
            body=bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body)>MAX_BYTES:
                    raise ValueError("response too large")
        offers=parse(json.loads(body))
        return ("retrieved" if offers else "no_offers"),offers
