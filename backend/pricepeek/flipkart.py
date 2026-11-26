"""Opt-in official affiliate integration; credentials remain server-side."""
import asyncio
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit
import httpx

ENDPOINT = "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"
MAX_BODY = 1_500_000

def configured():
    return (os.getenv("PRICEPEEK_FLIPKART_APPROVED") == "1"
            and bool(os.getenv("FLIPKART_AFFILIATE_ID"))
            and bool(os.getenv("FLIPKART_AFFILIATE_TOKEN")))

def parse(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("productInfoList"), list):
        raise ValueError("unexpected response")
    offers = []
    for item in payload["productInfoList"][:10]:
        if not isinstance(item, dict):
            continue
        p = item.get("productBaseInfoV1")
        if not isinstance(p, dict):
            continue
        amount = p.get("flipkartSellingPrice")
        if not isinstance(amount, dict) or amount.get("currency") != "INR":
            continue
        try:
            price = Decimal(str(amount.get("amount")))
            if not price.is_finite() or not 0 < price <= 100000000 or price != price.quantize(Decimal("0.01")):
                continue
        except (InvalidOperation, ValueError):
            continue
        url, title = p.get("productUrl"), p.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title.strip():
            continue
        try:
            u = urlsplit(url)
            if u.scheme not in ("http", "https") or u.netloc not in ("www.flipkart.com","flipkart.com","dl.flipkart.com"):
                continue
            url = urlunsplit(("https", u.netloc, u.path, u.query, ""))
        except ValueError:
            continue
        stock = p.get("inStock")
        offers.append({"name":title[:300], "brand":str(p.get("productBrand") or "")[:100],
                       "model":"", "gtin":"", "retailer_id":str(p.get("productId") or "")[:100],
                       "price_paise":int(price*100), "currency":"INR",
                       "availability":"InStock" if stock is True else "OutOfStock" if stock is False else "unknown",
                       "condition":"unknown", "url":url, "data_method":"affiliate_api"})
    return offers

async def fetch(client, query):
    if not configured():
        raise ValueError("adapter not approved")
    headers = {"Fk-Affiliate-Id":os.environ["FLIPKART_AFFILIATE_ID"],
               "Fk-Affiliate-Token":os.environ["FLIPKART_AFFILIATE_TOKEN"]}
    async with asyncio.timeout(12):
        async with client.stream("GET", ENDPOINT, params={"query":query,"resultCount":10},
                                 headers=headers, follow_redirects=False) as response:
            if response.status_code == 429:
                return "rate_limited", []
            if response.status_code in (401,403):
                return "authorization_required", []
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise ValueError("response too large")
        offers = parse(json.loads(body))
        return ("retrieved" if offers else "no_offers"), offers
