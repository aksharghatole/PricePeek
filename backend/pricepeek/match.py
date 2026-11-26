import re
import unicodedata

def tokens(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    # Treat common pack/storage spellings as equivalent without changing the unit.
    text = re.sub(r"(\d)\s+(gb|tb|mb|kg|mg|ml|g|l)\b", r"\1\2", text)
    return set(re.findall(r"[^\W_]+", text, flags=re.UNICODE))

def valid_gtin(code):
    return code.isascii() and code.isdigit() and len(code) in (8,12,13,14) and sum(int(n)*(3 if i%2 else 1) for i,n in enumerate(reversed(code)))%10==0

def classify(query, product):
    q = tokens(query)
    p = tokens(" ".join(str(product.get(k, "")) for k in ("name", "brand", "model", "gtin")))
    if not q or not q <= p:
        return "different"
    exclusions = {"case","cover","protector","compatible","refurbished","renewed","used","replica","skin"}
    if (p & exclusions) - q:
        return "different"
    condition = str(product.get("condition","")).casefold()
    if condition in {"usedcondition","refurbishedcondition","damagedcondition"} and not q & {"used","refurbished","renewed","damaged"}:
        return "different"
    gtin = str(product.get("gtin",""))
    if gtin in q and valid_gtin(gtin):
        return "identifier_match"
    # If the query specifies an explicit pack count, reject conflicting counts.
    def pack_counts(text):
        text=unicodedata.normalize("NFKC",text).casefold()
        return {int(n) for pair in re.findall(r"\bpack\s+of\s+(\d+)\b|\b(\d+)\s*(?:count|ct|pcs|pieces|pack)\b",text) for n in pair if n}
    requested=pack_counts(query)
    offered=pack_counts(str(product.get("name","")))
    if requested and offered and requested!=offered:
        return "different"
    # When a model identifier is in the query, do not silently include premium
    # or lite variants. Unqualified names remain candidates, never exact matches.
    model_query = any(re.search(r"[a-z]",t) and re.search(r"\d",t) and not re.fullmatch(r"\d+(gb|tb|mb|kg|mg|ml|g|l)",t) for t in q)
    if model_query and (p & {"ultra","plus","pro","max","lite","mini","fe"}) - q:
        return "different"
    return "candidate"
