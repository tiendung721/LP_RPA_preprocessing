from src.entity_extractor import EntityExtractor, OwnCompanyConfig


def extractor():
    return EntityExtractor(OwnCompanyConfig(["LE PHAM", "CTY TNHH LE PHAM", "CONG TY TNHH LE PHAM"], ["0200410388"], ["LE PHAM"]))


def test_extract_counterparty_after_thanh_toan_cho():
    entities = extractor().extract("ACB", "LE PHAM THANH TOAN CUOC VAN CHUYEN CHO VINH LONG THEO HD 127")
    assert entities.counterparty_hint == "VINH LONG"
    assert entities.counterparty_source == "thanh_toan_cho"


def test_extract_counterparty_after_ck_247_cho():
    entities = extractor().extract("MSB", "02101010072617-165842-CK 24/7 cho 0031000131428- CONG TY TNHH LE PHAM THANH TOAN TIEN MUA GIAY PHOTO CHO MEGAMARKET THEO HD 213585")
    assert entities.counterparty_hint == "MEGAMARKET"


def test_extract_counterparty_after_tt_cho():
    entities = extractor().extract("ACB", "TT CHO CT LOGISTICS HUY ANH HD 41")
    assert entities.counterparty_hint == "LOGISTICS HUY ANH"
