from pricepeek.openprices import parse,valid_barcode

def test_gtin():
    assert valid_barcode("4006381333931")
    assert not valid_barcode("4006381333932")
    assert not valid_barcode("1234")

def test_parse():
    code="4006381333931"
    row={"id":12,"product_code":code,"type":"PRODUCT","currency":"INR","price":"39.50",
         "date":"2025-01-02","location":{"osm_name":"Example Shop","osm_address_country_code":"IN"}}
    result=parse({"items":[row,{**row,"currency":"EUR"},{**row,"price_per":"KILOGRAM"},{**row,"product_code":"other"}]},code)
    assert len(result)==1
    assert result[0]["price_paise"]==3950 and result[0]["date"]=="2025-01-02"
