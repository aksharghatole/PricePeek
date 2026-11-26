"""Read-only WooCommerce Store API for explicitly authorized stores."""
import asyncio
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, quote_plus
import httpx

@dataclass(frozen=True)
class Store:
    name: str
    origin: str

def stores():
    # Operator-only configuration, never supplied by public API users.
    raw=os.getenv("PRICEPEEK_APPROVED_WOO_STORES","[]")
    data=json.loads(raw)
    if not isinstance(data,list) or len(data)>4:
        raise ValueError("configure at most four authorized stores")
    result=[]
    seen=set()
    for row in data:
        if not isinstance(row,dict) or row.get("approved") is not True:
            continue
        name,origin=row.get("name"),row.get("origin")
        if not isinstance(name,str) or not name.strip() or not isinstance(origin,str):
            raise ValueError("invalid store configuration")
        p=urlsplit(origin)
        # Only HTTPS DNS names; no ports, credentials, arbitrary paths or IP literals.
        if p.scheme!="https" or p.netloc!=p.hostname or not p.hostname or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",p.hostname) or p.path not in ("","/") or p.query or p.fragment:
            raise ValueError("invalid store origin")
        if p.hostname.endswith((".local",".internal",".localhost",".test",".invalid")) or p.hostname in seen:
            raise ValueError("invalid or duplicate store")
        seen.add(p.hostname)
        result.append(Store(name.strip()[:80],"https://"+p.hostname))
    return tuple(result)

def parse(data,store):
    if not isinstance(data,list):
        raise ValueError("unexpected WooCommerce response")
    offers=[]
    for row in data[:10]:
        if not isinstance(row,dict) or row.get("type")!="simple" or row.get("is_password_protected") is True:
            continue
        title,url,prices=row.get("name"),row.get("permalink"),row.get("prices")
        if not isinstance(title,str) or not title.strip() or not isinstance(url,str) or not isinstance(prices,dict):
            continue
        try:
            p=urlsplit(url)
            if p.scheme!="https" or p.netloc!=urlsplit(store.origin).netloc:
                continue
        except ValueError:
            continue
        # WooCommerce documents that prices are integer strings in currency minor units.
        value=prices.get("price")
        if prices.get("currency_code")!="INR" or prices.get("currency_minor_unit")!=2 or prices.get("price_range") is not None or not isinstance(value,str) or not re.fullmatch(r"[0-9]{1,11}",value):
            continue
        amount=int(value)
        if not 0<amount<=10_000_000_000:
            continue
        stock=row.get("is_in_stock")
        offers.append({"name":title.strip()[:300],"brand":"","model":"","gtin":"",
                       "retailer_id":str(row.get("sku") or row.get("id") or "")[:100],
                       "price_paise":amount,"currency":"INR","url":url,"condition":"unknown",
                       "availability":"InStock" if stock is True else "OutOfStock" if stock is False else "unknown",
                       "data_method":"retailer_api","variant":""})
    return offers

async def fetch(client,store,query):
    async with asyncio.timeout(12):
        async with client.stream("GET",store.origin+"/wp-json/wc/store/v1/products",
                                 params={"search":query,"per_page":10,"catalog_visibility":"visible"},
                                 follow_redirects=False,timeout=8) as r:
            if r.status_code==429:
                return "rate_limited",[]
            if r.status_code in (401,403):
                return "authorization_required",[]
            r.raise_for_status()
            data=bytearray()
            async for chunk in r.aiter_bytes():
                data.extend(chunk)
                if len(data)>1_500_000:
                    raise ValueError("response too large")
        offers=parse(json.loads(data),store)
        return ("retrieved" if offers else "no_offers"),offers

def search_url(store,query):
    return store.origin+"/?s="+quote_plus(query)+"&post_type=product"
