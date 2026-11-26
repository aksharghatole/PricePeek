# Cross-retailer expansion review — 2026-11-26

- Razorpay ACE Marketplace supports merchant-consented discovery across Indian merchants, but all tools need shopper OAuth sign-in. Not enabled; PricePeek is account-free. https://merchants.agent.razorpay.com/
- Shopify Global Catalog requires an app API key. Storefront Catalog uses a UCP agent profile and is merchant-specific. No integration claimed. https://shopify.dev/docs/agents/catalog/global-catalog and https://shopify.dev/docs/agents/catalog/storefront-catalog
- Jumpseller documents anonymous read-only product search intended for shopping assistants and comparison. Candidate for an Indian retailer after identifying an actual compatible INR store and verifying its response. https://jumpseller.com/support/storefront-mcp/
- PriceInIndia and CheapestInIndia remain potential sources pending usage clarification.

New comparison groups require a checksum-valid shared GTIN from at least two distinct source labels with matching reported condition and variant fields. This is an identifier match, not independently verified product equivalence. No best-price/savings claim is made when checkout costs are unknown. Current live CrowCrowCrow records lack GTIN, so appear as separate candidates. Simulated tests prove grouping logic; no live cross-retailer match is established.
