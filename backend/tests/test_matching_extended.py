from pricepeek.match import classify, tokens

def test_units():
    assert classify("Galaxy S25 256 GB",{"name":"Galaxy S25 256GB"})=="candidate"
    assert classify("butter 500 g",{"name":"Butter 500g"})=="candidate"
    assert classify("butter 500 g",{"name":"Butter 250g"})=="different"

def test_model_variants():
    assert classify("Galaxy S25",{"name":"Samsung Galaxy S25 Ultra"})=="different"
    assert classify("Galaxy S25 Ultra",{"name":"Samsung Galaxy S25 Ultra"})=="candidate"

def test_gtin_checksum():
    assert classify("4006381333931",{"name":"Product","gtin":"4006381333931"})=="identifier_match"
    assert classify("4006381333932",{"name":"Product","gtin":"4006381333932"})=="candidate"

def test_unicode():
    assert tokens("चाय") != set()
