# Optional shopping-web search pilot
SerpApi advertises 250 free searches per month and a Google Shopping result API.
https://serpapi.com/pricing
https://serpapi.com/shopping-results
https://serpapi.com/legal

To test: obtain a free account and check applicable terms and permitted display use. Configure SERPAPI_API_KEY and PRICEPEEK_SHOPPING_SEARCH_APPROVED=1 on the backend only. Never send the key to Android or commit it. No key is present and no paid account has been created. The free tier does not include Legal Shield. No live requests have been tested.

India search parameters: gl=in, hl=en, google_domain=google.co.in. The adapter retrieves a single result page on demand and accepts only explicit INR prices; rejects installments and second-hand flags. Search listings are NOT retailer-verified, stock and shipping remain unknown, and a link may open a search/product landing page. Store titles are candidates and require variant checking. Sources run concurrently with existing adapters.

Preview in-memory cap: 200 provider attempts per UTC month, reset by service restart; not a durable billing guard. Use the actual provider free-plan hard quota, disable any paid upgrades and do not expose unrestricted public search with a paid key. Public redistribution rights must be checked before release. No promises of comprehensive coverage.
