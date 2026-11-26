"""Conservative parsing of schema.org Product/Offer JSON-LD."""
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

def nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from nodes(item)
    elif isinstance(value, dict):
        yield value
        if "@graph" in value:
            yield from nodes(value["@graph"])

def has_type(obj, name):
    kind = obj.get("@type", [])
    return name in (kind if isinstance(kind, list) else [kind])

def same_host(url, base):
    a, b = urlsplit(url), urlsplit(base)
    return (a.scheme == "https" and a.netloc == b.netloc and
            a.hostname is not None and a.username is None and a.password is None)

def extract(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or script.get_text())
        except (ValueError, TypeError, RecursionError):
            continue
        for product in nodes(payload):
            if not has_type(product, "Product"):
                continue
            name = product.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            brand = product.get("brand", "")
            if isinstance(brand, dict):
                brand = brand.get("name", "")
            offers = product.get("offers", [])
            for offer in offers if isinstance(offers, list) else [offers]:
                if not isinstance(offer, dict) or not has_type(offer, "Offer"):
                    continue
                if offer.get("priceCurrency") != "INR":
                    continue
                try:
                    price = Decimal(str(offer.get("price")))
                    if not price.is_finite() or not Decimal("0") < price <= Decimal("100000000"):
                        continue
                    if price != price.quantize(Decimal("0.01")):
                        continue
                except (InvalidOperation, ValueError):
                    continue
                link = offer.get("url") or product.get("url") or page_url
                if not isinstance(link, str):
                    continue
                link = urljoin(page_url, link)
                if not same_host(link, page_url):
                    continue
                result.append({
                    "name": name.strip()[:300], "brand": str(brand)[:100],
                    "model": str(product.get("mpn") or product.get("model") or "")[:100],
                    "gtin": str(product.get("gtin13") or product.get("gtin14") or product.get("gtin") or ""),
                    "price_paise": int(price * 100), "currency": "INR",
                    "availability": str(offer.get("availability", "unknown")).split("/")[-1],
                    "condition": str(offer.get("itemCondition", "unknown")).split("/")[-1],
                    "url": link,
                })
    return result
