"""Operator-controlled sources. All live adapters disabled until reviewed."""
from dataclasses import dataclass
from urllib.parse import quote_plus, urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import asyncio
import httpx
from bs4 import BeautifulSoup
from .extract import extract, same_host

UA = "PricePeek/0.1"
MAX_BYTES = 1_500_000

@dataclass(frozen=True)
class Source:
    name: str
    search_template: str
    enabled: bool = False
    product_path_prefix: str = ""
    def search_url(self, query):
        return self.search_template.format(query=quote_plus(query))

SOURCES = (
    Source("Amazon India", "https://www.amazon.in/s?k={query}"),
    Source("Flipkart", "https://www.flipkart.com/search?q={query}"),
    Source("Croma", "https://www.croma.com/searchB?q={query}"),
    Source("Reliance Digital", "https://www.reliancedigital.in/search?q={query}"),
    Source("Vijay Sales", "https://www.vijaysales.com/search/{query}"),
)

async def get_text(client, url):
    async with client.stream("GET", url, follow_redirects=False) as response:
        response.raise_for_status()
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError("response exceeds limit")
        return body.decode(response.encoding or "utf-8", errors="replace")

async def scan(source, query, client, semaphore):
    url = source.search_url(query)
    if not source.enabled:
        return {"source": source.name, "status": "not_validated", "search_url": url, "offers": []}
    async with semaphore:
        try:
            async with asyncio.timeout(15):
                origin = urlsplit(url)
                if origin.scheme != "https" or origin.username or origin.password:
                    raise ValueError("invalid configured source")
                robot_url = f"https://{origin.netloc}/robots.txt"
                rules = RobotFileParser()
                rules.parse((await get_text(client, robot_url)).splitlines())
                if not rules.can_fetch(UA, url):
                    return {"source": source.name, "status": "disallowed", "search_url": url, "offers": []}
                html = await get_text(client, url)
                offers = extract(html, url)
                if source.product_path_prefix:
                    soup = BeautifulSoup(html, "html.parser")
                    links = []
                    for a in soup.find_all("a", href=True):
                        link = urljoin(url, a["href"]).split("#")[0]
                        if same_host(link, url) and urlsplit(link).path.startswith(source.product_path_prefix) and link not in links and rules.can_fetch(UA, link):
                            links.append(link)
                        if len(links) >= 3:
                            break
                    # Serial requests within one retailer; do not burst.
                    delay = rules.crawl_delay(UA) or 1
                    for link in links:
                        await asyncio.sleep(max(1, delay))
                        try:
                            offers.extend(extract(await get_text(client, link), link))
                        except (httpx.HTTPError, ValueError):
                            continue
                return {"source": source.name, "status": "retrieved" if offers else "no_offers", "search_url": url, "offers": offers}
        except (httpx.HTTPError, ValueError, TimeoutError):
            return {"source": source.name, "status": "unavailable", "search_url": url, "offers": []}
