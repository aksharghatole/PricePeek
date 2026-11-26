"""Operator-approved public web sources and optional official API."""
from dataclasses import dataclass, replace
from urllib.parse import quote_plus, quote, urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from .extract import extract, same_host
from . import flipkart

UA = "PricePeek/0.3 (+https://github.com/aksharghatole/PricePeek)"
ROBOT_UA = "PricePeek"
MAX_BYTES = 1_500_000

@dataclass(frozen=True)
class Source:
    name: str
    search_template: str
    enabled: bool = False
    product_path_prefix: str = ""
    slug: str = ""
    def search_url(self, query):
        value = quote(query, safe="") if "?" not in self.search_template else quote_plus(query)
        return self.search_template.format(query=value)

DEFAULT_SOURCES = (
    Source("Amazon India", "https://www.amazon.in/s?k={query}", slug="amazon"),
    Source("Flipkart", "https://www.flipkart.com/search?q={query}", slug="flipkart"),
    Source("Croma", "https://www.croma.com/searchB?q={query}", slug="croma"),
    Source("Reliance Digital", "https://www.reliancedigital.in/search?q={query}", slug="reliance"),
    Source("Vijay Sales", "https://www.vijaysales.com/search/{query}", slug="vijaysales"),
)
def configured_sources():
    configured = []
    for source in DEFAULT_SOURCES:
        key = "PRICEPEEK_WEB_" + source.slug.upper()
        # Search template is fixed in code. Only a reviewed product path may be supplied.
        prefix = os.getenv(key + "_PRODUCT_PREFIX", "")
        if prefix and (not prefix.startswith("/") or prefix == "/" or "//" in prefix or any(c in prefix for c in "?&#%\\") or ".." in prefix):
            raise ValueError("invalid product path prefix for " + source.slug)
        enabled = os.getenv(key + "_APPROVED") == "1"
        configured.append(replace(source, enabled=enabled, product_path_prefix=prefix))
    return tuple(configured)

SOURCES = configured_sources()
locks = {source.name: asyncio.Lock() for source in SOURCES}
next_request = {}

async def get_text(client, url):
    async with client.stream("GET", url, follow_redirects=False) as response:
        response.raise_for_status()
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError("response exceeds limit")
        return body.decode(response.encoding or "utf-8", errors="replace")

def batch(source, query, status, offers=None):
    return {"source":source.name,"status":status,"search_url":source.search_url(query),"offers":offers or []}

def product_links(html, url, prefix, rules):
    if not prefix:
        return []
    links = []
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        try:
            link = urljoin(url, a["href"]).split("#")[0]
            path = urlsplit(link).path
            if same_host(link, url) and (path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/")) and link not in links and rules.can_fetch(ROBOT_UA, link):
                links.append(link)
        except ValueError:
            continue
        if len(links) >= 3:
            break
    return links

async def web_scan(source, query, client, pace):
    url = source.search_url(query)
    origin = urlsplit(url)
    if origin.scheme != "https" or origin.username or origin.password:
        raise ValueError("invalid configured source")
    rules = RobotFileParser()
    rules.parse((await get_text(client, f"https://{origin.netloc}/robots.txt")).splitlines())
    if not rules.can_fetch(ROBOT_UA, url):
        return "disallowed", [], 60
    rate = rules.request_rate(ROBOT_UA)
    delay = max(2.0, float(rules.crawl_delay(ROBOT_UA) or 0), rate.seconds / rate.requests if rate and rate.requests else 0)
    # Respect pacing between the robots, search and product requests.
    await pace(delay)
    html = await get_text(client, url)
    offers = extract(html, url)
    for link in product_links(html, url, source.product_path_prefix, rules):
        await pace(delay)
        # Stop on any error, rather than retrying or evading a block.
        offers.extend(extract(await get_text(client, link), link))
    for offer in offers:
        offer["data_method"] = "public_web"
    return ("retrieved" if offers else "no_offers"), offers, delay

async def scan(source, query, client, semaphore):
    official = source.name == "Flipkart" and flipkart.configured()
    if not source.enabled and not official:
        return batch(source, query, "not_validated")
    lock = locks.setdefault(source.name, asyncio.Lock())
    if lock.locked():
        return batch(source, query, "busy")
    async with lock, semaphore:
        now = asyncio.get_running_loop().time()
        if now < next_request.get(source.name, 0):
            return batch(source, query, "cooldown")
        try:
            async with asyncio.timeout(15):
                if official:
                    status, offers = await flipkart.fetch(client, query)
                    delay = 60 if status in ("rate_limited", "authorization_required") else 2
                else:
                    status, offers, delay = await web_scan(source, query, client, asyncio.sleep)
        except httpx.HTTPStatusError as exc:
            status = "rate_limited" if exc.response.status_code == 429 else "disallowed" if exc.response.status_code in (401,403) else "unavailable"
            offers, delay = [], 60
        except (httpx.HTTPError, ValueError, TimeoutError):
            status, offers, delay = "unavailable", [], 60
        next_request[source.name] = asyncio.get_running_loop().time() + delay
        return batch(source, query, status, offers)
