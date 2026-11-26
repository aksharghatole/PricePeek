# Retailer validation gate

Current status: no retailer validated. Search links are convenience links only and their current behavior is untested.

For each candidate, record:
- Official terms / authorized API or feed and permission basis; robots policy for exact automated paths.
- Search URL and product URL patterns; redirects and public availability.
- INR price, product identifier, stock, condition, location and conditional discount behavior.
- 5–10 sample products, direct page vs extracted price, observed latency and errors.
- A decision: approved adapter, link-only, or unavailable.

Do not enable an adapter just because a page is public. Do not bypass blocks, CAPTCHAs or login requirements. Do not request users' retailer credentials.

Initial target: 50 manually checked product searches across up to 10 candidates, at least 3 reliable permitted retailers before calling the comparison feature ready. Exact-match groups require verified identifiers and compatible variants.

Future engineering: per-source throttling across concurrent requests, request coalescing, rate limits at deployment, egress controls, source allowlist, no arbitrary URL fetching, Android app, price history. Public deployment is gated on these protections and live adapter validation.
