# PricePeek
Search once. Compare everywhere.

Android-first, India-focused, on-demand shopping comparison. No account or paid data dependency for the initial version.

## Status
Backend and Android client source are implemented. No live retailer has yet passed access and accuracy validation. Search links are not offers and never contain invented prices. Android CI produces a debug APK when successful; no hosted service is configured yet.

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
- Conservative identity matching: all requested tokens, accessory and condition checks, with barcode-based identifier matches separated from title-based candidates.
- A bounded 15-minute in-memory search cache is implemented; the Android client supports local search links and an optional HTTPS backend. No background scraping or bypassing restrictions.

Run tests: `cd backend && python -m pytest -q`.

See [retailer validation](docs/retailer-validation.md) before enabling any live source.

## Android
Android 8+. Open GitHub Actions → Android APK → successful run → PricePeek-debug-apk artifact. The app works in retailer-link mode without a backend. In Settings, enter your trusted HTTPS PricePeek backend origin to enable offer retrieval. Shared text can prefill a product name; URL-only shares require manual product identification. Search history is local and can be cleared. See [data source research](docs/data-source-research.md).

## Optional official Flipkart adapter
After obtaining authorized credentials and confirming permitted Android use, configure server environment variables `PRICEPEEK_FLIPKART_APPROVED=1`, `FLIPKART_AFFILIATE_ID`, and `FLIPKART_AFFILIATE_TOKEN`. Never commit credentials. Without all three, Flipkart stays link-only. The adapter uses standard selling price, not special price or MRP. Live credentials and results remain unverified. See https://affiliate.flipkart.com/api-docs/af_prod_ref.html .
