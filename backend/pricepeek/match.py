import re

def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold()))

def classify(query, product):
    q = tokens(query)
    p = tokens(" ".join(str(product.get(k, "")) for k in ("name", "brand", "model", "gtin")))
    if not q or not q <= p:
        return "different"
    # Accessories and used/refurbished products are not equivalent to new products.
    exclusions = {"case", "cover", "protector", "compatible", "refurbished", "renewed", "used", "replica", "skin"}
    if (p & exclusions) - q:
        return "different"
    condition = str(product.get("condition", "")).casefold()
    if condition in {"usedcondition", "refurbishedcondition", "damagedcondition"} and not q & {"used", "refurbished", "renewed", "damaged"}:
        return "different"
    # Do not claim exact equivalence based on overlapping title text alone.
    gtin = str(product.get("gtin", ""))
    if gtin and gtin in q and gtin.isdigit() and len(gtin) in (8, 12, 13, 14):
        return "identifier_match"
    return "candidate"
