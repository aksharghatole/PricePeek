from fastapi import FastAPI
from fastapi.testclient import TestClient
from pricepeek.limits import SearchLimits

def test_rate_limit():
    app=FastAPI()
    app.add_middleware(SearchLimits,maximum=2)
    @app.get("/v1/search")
    def search():
        return {"ok":True}
    @app.get("/health")
    def health():
        return {"ok":True}
    with TestClient(app) as client:
        assert client.get("/v1/search").status_code==200
        assert client.get("/v1/search").status_code==200
        assert client.get("/v1/search").status_code==429
        assert client.get("/health").status_code==200
