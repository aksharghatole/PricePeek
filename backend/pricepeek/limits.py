"""Single-process preview request controls; reset on restart."""
from collections import deque
from time import monotonic
import asyncio
from starlette.responses import JSONResponse

class SearchLimits:
    def __init__(self, app, maximum=30, window=60, concurrency=4):
        self.app=app
        self.maximum=maximum
        self.window=window
        self.concurrency=concurrency
        self.recent=deque()
        self.active=0
        self.lock=asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http" or scope["path"] not in ("/v1/search","/v1/observations"):
            await self.app(scope,receive,send)
            return
        async with self.lock:
            now=monotonic()
            while self.recent and self.recent[0]<=now-self.window:
                self.recent.popleft()
            rejected=len(self.recent)>=self.maximum or self.active>=self.concurrency
            if not rejected:
                self.recent.append(now)
                self.active+=1
        if rejected:
            await JSONResponse({"detail":"Preview search capacity reached; try again later."},status_code=429,headers={"Retry-After":"60"})(scope,receive,send)
            return
        try:
            await self.app(scope,receive,send)
        finally:
            async with self.lock:
                self.active-=1
