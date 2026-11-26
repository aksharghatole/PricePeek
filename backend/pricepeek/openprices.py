"""Separate ODbL community price observations, not live retailer offers."""
import json
from decimal import Decimal, InvalidOperation
from datetime import date
import httpx

URL = "https://prices.openfoodfacts.org/api/v1/prices"
ATTRIBUTION = "Open Prices / Open Food Facts (ODbL); location data OpenStreetMap contributors"

def valid_barcode(code):
    if len(code) not in (8,12,13,14) or not code.isascii() or not code.isdigit():
        return False
    return sum(int(n)*(3 if i%2 else 1) for i,n in enumerate(reversed(code)))%10 == 0

def parse(payload, code):
    items = payload.get("items") if isinstance(payload,dict) else None
    if not isinstance(items,list):
        raise ValueError("unexpected response")
    result=[]
    for p in items[:50]:
        if not isinstance(p,dict) or p.get("product_code")!=code or p.get("currency")!="INR" or p.get("type")!="PRODUCT":
            continue
        if p.get("price_per") not in (None,"UNIT"):
            continue
        try:
            amount=Decimal(str(p.get("price")))
            observed=date.fromisoformat(p.get("date",""))
            if not amount.is_finite() or not 0<amount<=100000000 or amount!=amount.quantize(Decimal("0.01")) or observed>date.today():
                continue
        except (InvalidOperation,ValueError,TypeError):
            continue
        loc=p.get("location") or {}
        prod=p.get("product") or {}
        if not isinstance(loc,dict) or not isinstance(prod,dict):
            continue
        if loc.get("osm_address_country_code") not in ("IN","in",None,""):
            continue
        ident=p.get("id")
        if not isinstance(ident,int) or ident<=0:
            continue
        result.append({"name":str(prod.get("product_name") or p.get("product_name") or code)[:200],
                       "store":str(loc.get("osm_name") or loc.get("osm_brand") or "Unknown store")[:150],
                       "city":str(loc.get("osm_address_city") or "")[:100],
                       "price_paise":int(amount*100),"currency":"INR","date":observed.isoformat(),
                       "discounted":p.get("price_is_discounted") is True,
                       "url":f"https://prices.openfoodfacts.org/prices/{ident}"})
    return sorted(result,key=lambda x:x["date"],reverse=True)

async def fetch(client,code):
    async with client.stream("GET",URL,params={"product_code":code,"currency":"INR","kind":"COMMUNITY","size":30,"order_by":"-date"},follow_redirects=False) as response:
        response.raise_for_status()
        body=bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body)>1_500_000:
                raise ValueError("response too large")
    return parse(json.loads(body),code)
