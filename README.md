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

## Optional shopping web pilot
An opt-in Google Shopping search provider now supports India-focused multi-store search listings via SerpApi's free-plan allowance. No live credentials or approval configured. See [setup and limitations](docs/shopping-search.md). The Android UI labels these as unverified web search listings, never guaranteed live retailer prices.

## Android 0.4.0 — keyless listing import
No SerpApi key is required. Optional provider remains disabled. Copy visible product text from a browser or share it to PricePeek. The app proposes a price only for one explicit INR amount with no obvious conditional/discount language; you must review the title, retailer, price and fees before saving locally. Multiple amounts remain blank for manual review. No automated access or scraping is performed by this feature. This is browser-assisted comparison, not automatic multi-retailer price retrieval.

## Keyless retailer catalogue
CrowCrowCrow documents a public, anonymous, read-only MCP for product discovery and shopping agents linking users to its store: https://crowcrowcrow.com/mcp . The PricePeek integration uses only documented initialization and products.search, five results per search, a per-source lock and cooldown, INR prices and same-retailer product links. Enabled by default; `PRICEPEEK_CCC_DISABLED=1` disables it. Its imported-product catalogue is a single retailer, not Amazon or Flipkart prices. No bulk crawling, account, key or purchase actions. Live verification via Keyless retailer live probe workflow is pending. SerpApi stays disabled. Other retailer sources still require validation.

## Keyless integration expansion
The CrowCrowCrow live probe at https://github.com/aksharghatole/PricePeek/actions/runs/45777576834 passed on 2026-11-26 and returned five catalogue records for `protein bar`. These are different products and pack sizes, not equivalent offers. Added opt-in WooCommerce Store API support for authorized independent retailers, with no key and mocked tests. See [store setup](docs/woocommerce.md). No WooCommerce store has been approved yet. SerpApi remains unused.

## Android 0.5.0 — comparison groups
The API groups offers only when at least two distinct retailer labels report the same valid GTIN with compatible reported condition and variant fields. Other product listings remain separate and clearly labeled. A hosted keyless verification workflow tests real catalogue retrieval through Render. See [multi-retailer roadmap](docs/multi-retailer-roadmap.md). No live cross-retailer comparison has been established yet.

## Optional PriceInIndia keyless evaluation
A documented public MCP adapter is ready for evaluation, with observation timestamps, preserved source attribution and affiliate redirects. Public use remains disabled pending terms review. See [details](docs/priceinindia.md). SerpApi remains unused.
