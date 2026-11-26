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

## Direct web adapters and hosting
Direct web adapters now support operator-configured approval flags and reviewed product-path prefixes, with tests for robots policy and extraction. See [web validation](docs/web-validation.md). A free-plan Render blueprint is included but not deployed. All direct sources remain disabled by default.

## Optional PriceYuge comparison provider
Set `PRICEPEEK_DATAYUGE_APPROVED=1` and `DATAYUGE_API_KEY` only after authorized registration and free-plan confirmation. The adapter uses at most two requests per search and a conservative in-memory 80-call daily budget; this resets if the process restarts. The provider's prices are snapshots, typically updated daily, not live checkout prices. Affiliate redirects are preserved. See https://price-api.datayuge.com/docs/ . Preview ingress is limited to 30 searches per minute globally and four concurrent searches per process. No live credentials are configured.

## Hosted preview and open observations
The default Android backend is https://pricepeek-api-w4qr.onrender.com . Clear the server address in Settings to use local retailer links only. Numeric GTIN searches use a separate `/v1/observations?barcode=...` endpoint for historical community observations in INR from Open Prices, with ODbL attribution and links. Not live online offers; India coverage may be sparse. No external API key needed. No live response has been independently verified yet. API: https://openfoodfacts.github.io/documentation/docs/Open-prices/prices/prices_list/ . Data license: https://openfoodfacts.github.io/open-prices/guides/data/ .

## Android 0.2.0
Scan physical product barcodes using the on-device ZXing scanner (camera permission only when scanning). Share a product title or supported retailer URL; PricePeek suggests a title from the URL path locally and lets you edit it. Bare IDs and shortened URLs require the product name. No URL fetching or redirects are used for identification. See [live source review](docs/live-source-review.md).

## Android 0.3.0
Manual price notebook: compare user-entered prices including delivery/fees, sorted by total within the same product label, stored locally (up to 200 entries). These are not automatically verified offers. Shopping web search opens a browser; no scraping is performed by this feature. Hosted API smoke workflow tests the deployed URL, including invalid barcode handling. The source-matching update normalizes common unit spacing and rejects additional model suffixes conservatively. The main limitation remains live automated retailer access.
