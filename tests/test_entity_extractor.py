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


def test_extract_company_prefix_without_legal_suffix():
    entities = extractor().extract(
        "VCB",
        "6093ABBKA215JUJJ.Cty Vu Gia Tam thanh toan phi dai ly.20260403.171402",
    )
    assert entities.counterparty_hint == "VU GIA TAM"


def test_clean_msb_counterparty_raw_account_prefix():
    entities = extractor().extract(
        "MSB",
        "TT VNMN391NO N VNPA",
        "00158412779617001 S5 VIET NAM COMPANY LIMITED",
    )
    assert entities.counterparty_hint == "S5 VIET NAM"


def test_extract_new_acb_counterparty_patterns():
    cases = [
        ("TCL SMART DEVICE VIET NAM COMPANY LIMITED-TIEN COC", "TCL SMART DEVICE VIET NAM"),
        ("CP VIETNAM CORPORATION-553 VOI HOT-TA 25KGBAO CHARGEDETAILS OUR", "CP VIETNAM CORPORATION"),
        ("CO SO THANH PHONG CHUYEN TIEN GD 6135IBT1CJ1HNHAG", "CO SO THANH PHONG"),
        ("CT TNHH LE PHAM TT TIENHANG CHO CT VIET THANG", "VIET THANG"),
        ("CT TNHH LE PHAM TT CANG GAMA. TAU EAGLE AROW, ST 22376.67", "GAMA"),
        ("LE PHAM CT CHO VOI VIET-150526-11:34:00", "VOI VIET"),
    ]
    for description, expected_hint in cases:
        entities = extractor().extract("ACB", description)
        assert entities.counterparty_hint == expected_hint


def test_extract_cash_person_name_from_cash_descriptions():
    cases = [
        "LE THI THANH HOA#001178043963#CHI SEC 22541668#1156992 ;",
        "LE THI THANH HOA#001178043963#NT#12739876;12739876-NT-TK-ACB-1794027",
    ]
    for description in cases:
        entities = extractor().extract("ACB", description)
        assert entities.cash_person_name == "LE THI THANH HOA"
        assert entities.cash_person_source == "acb_cash_marker"
