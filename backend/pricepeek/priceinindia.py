"""Optional documented public MCP. Not enabled without operator review."""
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import httpx
from .crowcrowcrow import rpc

ENDPOINT="https://mcp.priceinindia.website/mcp"
HOSTS={"priceinindia.website","www.priceinindia.website","mcp.priceinindia.website"}

def configured():
    return os.getenv("PRICEPEEK_PRICEININDIA_APPROVED")=="1"

def safe_link(value):
    if not isinstance(value,str):
        return False
    try:
        p=urlsplit(value)
        return p.scheme=="https" and p.hostname in HOSTS and p.username is None and p.password is None and p.port in (None,443)
    except ValueError:
        return False

def rows(value,depth=0):
    if depth>4:
        return []
    if isinstance(value,list):
        return [x for x in value[:20] if isinstance(x,dict)]
    if not isinstance(value,dict):
        return []
    if "title" in value and "price" in value:
        return [value]
    for key in ("products","items","results","data"):
        if key in value:
            return rows(value[key],depth+1)
    return []

def parse(result):
    if not isinstance(result,dict) or result.get("isError"):
        raise ValueError("provider error")
    items=rows(result.get("structuredContent"))
    if not items:
        for p in result.get("content",[])[:3]:
            if isinstance(p,dict) and p.get("type")=="text":
                try:
                    items.extend(rows(json.loads(p.get("text",""))))
                except (ValueError,TypeError):
                    continue
    offers=[]
    for row in items[:20]:
        title,store=row.get("title"),row.get("store")
        url,citation=row.get("productUrl"),row.get("productPageUrl")
        if not isinstance(title,str) or not title.strip() or not isinstance(store,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{1,100}",store):
            continue
        if row.get("currency")!="INR" or not safe_link(url) or not safe_link(citation):
            continue
        try:
            amount=Decimal(str(row.get("price")))
            if not amount.is_finite() or not 0<amount<=100000000 or amount!=amount.quantize(Decimal("0.01")):
                continue
            stamp=row.get("lastUpdated")
            if not isinstance(stamp,(int,float)) or isinstance(stamp,bool):
                continue
            observed=datetime.fromtimestamp(stamp,timezone.utc)
            now=datetime.now(timezone.utc)
            if observed.year<2020 or (observed-now).total_seconds()>300:
                continue
        except (InvalidOperation,ValueError,OverflowError,OSError):
            continue
        stock=row.get("outOfStock")
        offers.append({"name":title[:300],"source":store.lower(),"brand":str(row.get("brand") or "")[:100],
                       "model":"","gtin":"","price_paise":int(amount*100),"currency":"INR","url":url,
                       "citation_url":citation,"observed_at":observed.isoformat(),"condition":"unknown",
                       "availability":"OutOfStock" if stock is True else "InStock" if stock is False else "unknown",
                       "data_method":"priceinindia_snapshot","variant":""})
    return offers

def retry_delay(value):
    try:
        return max(60,int(value))
    except (ValueError,TypeError):
        try:
            return max(60,int((parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()))
        except (ValueError,TypeError,OverflowError):
            return 60

async def fetch(client,query):
    session={}
    async with asyncio.timeout(20):
        try:
            init,sid=await rpc(client,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
                "protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"PricePeek","version":"0.11.0"}}},session,1,ENDPOINT)
            version=(init.get("result") or {}).get("protocolVersion")
            if init.get("error") or version not in ("2024-11-05","2025-03-26","2025-06-18","2025-11-25"):
                raise ValueError("MCP initialization failed")
            session["MCP-Protocol-Version"]=version
            if sid:
                session["Mcp-Session-Id"]=sid
            await rpc(client,{"jsonrpc":"2.0","method":"notifications/initialized"},session,None,ENDPOINT)
            data,_=await rpc(client,{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
                "name":"search_products","arguments":{"query":query,"per_page":10,"page":1,"sort":"relevance"}}},session,2,ENDPOINT)
            if data.get("error"):
                raise ValueError("MCP search failed")
            offers=parse(data.get("result"))
            return ("retrieved" if offers else "no_offers"),offers,10
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==429:
                return "rate_limited",[],retry_delay(exc.response.headers.get("Retry-After"))
            if exc.response.status_code in (401,403):
                return "authorization_required",[],60
            raise
        finally:
            if "Mcp-Session-Id" in session:
                try:
                    await client.delete(ENDPOINT,headers=session,timeout=2,follow_redirects=False)
                except httpx.HTTPError:
                    pass
