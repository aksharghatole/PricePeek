# Live price access review (2026-11-26)

The direct-web adapters remain disabled: no validated permission or successful retailer test yet.
- CheapestInIndia offers a no-key read-only MCP integration for AI assistants; its terms restrict scraping/bulk downloads and reserve site content and price-history data. Standalone public app integration requires clarification: https://www.cheapestinindia.com/terms
- PriceInIndia publishes a no-key MCP endpoint for AI assistants; standalone redistribution permission not established: https://www.priceinindia.website/mcp
- OpenMRP is an ODbL product/MRP registry, not a current retailer offer feed. Its API needs a free key and the README describes a pre-launch status: https://github.com/openmrp-in/openmrp . No production availability assumed.
- Open Prices remains a separate historical barcode observation source.

No scraping restrictions are bypassed, no accounts or paid services created. The app now has a local barcode camera scanner and editable product-name suggestions from supported retailer URL paths. A short link or bare product identifier cannot establish the name and is not followed automatically.
