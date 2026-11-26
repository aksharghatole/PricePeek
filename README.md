# PricePeek
Search once. Compare everywhere.

Android-first, India-focused, on-demand shopping comparison. No account or paid data dependency for the initial version.

## Status
Backend foundation only. No live retailer has yet passed access and accuracy validation. Search links are not offers and never contain invented prices. The Android APK and hosted service are not available yet.

## Run locally
```sh
cd backend
python -m venv .venv
# activate the environment
pip install -r requirements.txt
uvicorn pricepeek.api:app --reload
```
Open http://127.0.0.1:8000/docs or request /v1/search?q=Logitech%20G304. With no approved adapters, the response contains search links and source status, not prices.

## Design
- Explicit, operator-reviewed retailer configurations; no arbitrary user URL fetching.
- On-demand search, bounded concurrency, same-host HTTPS only, robots checks, no redirect following, bounded response sizes and timeouts.
- JSON-LD Product/Offer extraction; INR only; no speculative price conversion.
- Conservative identity matching: all requested tokens, explicit model/variant identifiers, accessory and condition checks. Only confirmed identifiers qualify as exact matches.
- Cache and Android app are next milestones. No background scraping or bypassing restrictions.

Run tests: `cd backend && python -m pytest -q`.

See [retailer validation](docs/retailer-validation.md) before enabling any live source.
