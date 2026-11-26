"""Do not group title matches as identical products."""
from collections import defaultdict
from .match import valid_gtin

def assign_groups(offers):
    buckets=defaultdict(list)
    for offer in offers:
        offer.pop("comparison_group",None)
        gtin=str(offer.get("gtin") or "")
        if not valid_gtin(gtin) or not int(gtin):
            continue
        # GTINs of different lengths may represent the same item when zero padded.
        # Keep different explicitly reported variants/conditions separate.
        variant=str(offer.get("variant") or "").strip().casefold()
        condition=str(offer.get("condition") or "unknown").strip().casefold()
        key=(gtin.zfill(14),variant,condition)
        buckets[key].append(offer)
    count=0
    for key,items in sorted(buckets.items()):
        sources={str(x.get("source") or "").strip().casefold() for x in items}
        sources.discard("")
        if len(sources)<2:
            continue
        count+=1
        for item in items:
            item["comparison_group"]="gtin-"+str(count)
    return count
