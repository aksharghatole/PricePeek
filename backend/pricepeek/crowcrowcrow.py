"""Documented, anonymous, read-only retailer MCP; no account or API key."""
import asyncio
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import httpx

ENDPOINT = "https://crowcrowcrow.com/api/mcp/mcp"
MAX_BYTES = 1_000_000

def configured():
    return os.getenv("PRICEPEEK_CCC_DISABLED", "0") != "1"

def parse_rows(value, depth=0):
    if depth > 4:
        return []
    if isinstance(value,list):
        return [x for x in value[:20] if isinstance(x,dict)]
    if not isinstance(value,dict):
        return []
    if "title" in value and "price" in value:
        return [value]
    for key in ("products","items","results","data"):
        if key in value:
            return parse_rows(value[key],depth+1)
    return []

def parse(result):
    if not isinstance(result,dict) or result.get("isError"):
        raise ValueError("retailer MCP error")
    rows=parse_rows(result.get("structuredContent"))
    if not rows:
        for part in result.get("content",[])[:3]:
            if isinstance(part,dict) and part.get("type")=="text":
                try:
                    rows.extend(parse_rows(json.loads(part.get("text",""))))
                except (ValueError,TypeError):
                    continue
    offers=[]
    for row in rows[:10]:
        title,url,p=row.get("title"),row.get("url"),row.get("price")
        if not isinstance(title,str) or not title.strip() or not isinstance(url,str) or not isinstance(p,dict) or p.get("currency")!="INR":
            continue
        try:
            link=urlsplit(url)
            if link.scheme!="https" or link.netloc not in ("crowcrowcrow.com","www.crowcrowcrow.com") or not link.path.startswith("/p/"):
                continue
            price=Decimal(str(p.get("price")))
            if not price.is_finite() or not 0<price<=100000000 or price!=price.quantize(Decimal("0.01")):
                continue
        except (InvalidOperation,ValueError):
            continue
        stock=row.get("inStock")
        offers.append({"name":title[:300],"brand":str(row.get("brand") or "")[:100],"model":"","gtin":"",
                       "retailer_id":str(row.get("sku") or "")[:100],"price_paise":int(price*100),
                       "currency":"INR","url":url,"condition":"unknown",
                       "availability":"InStock" if stock is True else "OutOfStock" if stock is False else "unknown",
                       "data_method":"retailer_mcp","variant":""})
    return offers

async def rpc(client, payload, session_headers, expected):
    headers={"Accept":"application/json, text/event-stream","Content-Type":"application/json",**session_headers}
    async with client.stream("POST",ENDPOINT,json=payload,headers=headers,follow_redirects=False,timeout=8) as response:
        response.raise_for_status()
        sid=response.headers.get("Mcp-Session-Id")
        if expected is None:
            return None,sid
        content_type=response.headers.get("content-type","").lower()
        if "text/event-stream" in content_type:
            total=0
            lines=[]
            async for line in response.aiter_lines():
                total+=len(line.encode("utf-8"))+1
                if total>MAX_BYTES:
                    raise ValueError("MCP response too large")
                if line.startswith("data:"):
                    lines.append(line[5:].lstrip())
                elif not line and lines:
                    data=json.loads("\n".join(lines))
                    lines=[]
                    if isinstance(data,dict) and data.get("id")==expected:
                        return data,sid
            if lines:
                data=json.loads("\n".join(lines))
                if isinstance(data,dict) and data.get("id")==expected:
                    return data,sid
            raise ValueError("no matching MCP response")
        if "application/json" not in content_type:
            raise ValueError("unexpected MCP content type")
        body=bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body)>MAX_BYTES:
                raise ValueError("MCP response too large")
        data=json.loads(body)
        if not isinstance(data,dict) or data.get("id")!=expected:
            raise ValueError("unexpected MCP message")
        return data,sid

async def fetch(client,query):
    if not configured():
        return "not_validated",[]
    session={}
    async with asyncio.timeout(20):
        try:
            init,sid=await rpc(client,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
                "protocolVersion":"2024-11-05","capabilities":{},
                "clientInfo":{"name":"PricePeek","version":"0.8.0"}}},session,1)
            version=(init.get("result") or {}).get("protocolVersion")
            if init.get("error") or version not in ("2024-11-05","2025-03-26","2025-06-18","2025-11-25"):
                raise ValueError("MCP initialization failed")
            session["MCP-Protocol-Version"]=version
            if sid:
                session["Mcp-Session-Id"]=sid
            await rpc(client,{"jsonrpc":"2.0","method":"notifications/initialized"},session,None)
            data,_=await rpc(client,{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
                "name":"products.search","arguments":{"query":query,"limit":5}}},session,2)
            if data.get("error"):
                raise ValueError("MCP search failed")
            offers=parse(data.get("result"))
            return ("retrieved" if offers else "no_offers"),offers
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==429:
                return "rate_limited",[]
            if exc.response.status_code in (401,403):
                return "authorization_required",[]
            raise
        finally:
            # Stateful servers can release resources; no retries or other writes.
            if "Mcp-Session-Id" in session:
                try:
                    await client.delete(ENDPOINT,headers=session,timeout=2,follow_redirects=False)
                except httpx.HTTPError:
                    pass
