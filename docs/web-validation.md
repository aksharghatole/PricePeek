# Direct web validation and deployment
For a candidate retailer, verify the site's terms and permission for this exact integration. Record approved search and product URLs, robots rules, observed prices versus checkout, product variants and stock. None has passed live validation yet.

Once approved, configure the server:
- PRICEPEEK_WEB_CROMA_APPROVED=1 (example name only; not approval)
- PRICEPEEK_WEB_CROMA_PRODUCT_PREFIX=/reviewed-prefix (optional; if omitted only search-page JSON-LD is read)
Supported slugs: AMAZON, FLIPKART, CROMA, RELIANCE, VIJAYSALES. Search domains are fixed in code. Do not set approval flags until the actual source is reviewed. The official Flipkart adapter takes precedence when configured.

The parser reads the exact robots policy and limits links to the reviewed path, respects crawl delay and request rate, uses one request stream per retailer and stops on an access error. The tests use synthetic HTML with a mock HTTP transport, not live retailer access.

Render blueprint is for a free single-worker preview; do not deploy for unrestricted public traffic before adding ingress rate limits and completing live source validation. No credentials or approval flags are included. Configure the HTTPS backend in Android settings for testing.
