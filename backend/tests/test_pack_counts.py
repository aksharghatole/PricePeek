from pricepeek.match import classify

def test_conflicting_pack_counts():
    assert classify("Protein bar pack of 12",{"name":"Protein bar pack of 12 plus 6 count"})=="different"
    assert classify("Protein bar pack of 12",{"name":"Protein bar pack of 12"})=="candidate"
