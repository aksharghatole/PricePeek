from pricepeek.comparison import assign_groups

def offer(source,**extra):
    return {"gtin":"4006381333931","source":source,"name":"Example X100","condition":"unknown",**extra}

def test_cross_store_only():
    items=[offer("A"),offer("B"),offer("A",variant="red"),offer("C",condition="UsedCondition")]
    assert assign_groups(items)==1
    assert items[0]["comparison_group"]==items[1]["comparison_group"]
    assert "comparison_group" not in items[2] and "comparison_group" not in items[3]

def test_title_and_same_retailer_not_enough():
    items=[offer("A",gtin=""),offer("B",gtin=""),offer("C"),offer("c")]
    assert assign_groups(items)==0
    assert all("comparison_group" not in x for x in items)

def test_zero_padding_and_invalid():
    items=[offer("A"),offer("B",gtin="04006381333931"),offer("C",gtin="4006381333932")]
    assert assign_groups(items)==1
    assert "comparison_group" not in items[2]
