from datetime import date

from src.normalizer import normalize_text, parse_amount, parse_date


def test_normalize_vietnamese_text():
    assert normalize_text("Nộp thuế GTGT tháng 03/2026") == "NOP THUE GTGT THANG 03 2026"


def test_normalize_standard_vietnamese_text():
    assert normalize_text("Công ty cổ phần xi măng Sông Lam") == "CONG TY CO PHAN XI MANG SONG LAM"


def test_normalize_tcvn3_catalog_text():
    assert normalize_text("C«ng ty cæ phÇn xi m¨ng S«ng Lam") == "CONG TY CO PHAN XI MANG SONG LAM"


def test_normalize_tcvn3_catalog_text_with_uong():
    assert normalize_text("§¹i Lý Hµng H¶i §­êng BiÓn") == "DAI LY HANG HAI DUONG BIEN"


def test_normalize_business_typos_and_abbreviations():
    assert normalize_text("THANH TON TIEN THUE") == "THANH TOAN TIEN THUE"
    assert normalize_text("TT TIENHANG CHO NCC") == "TT TIEN HANG CHO NCC"
    assert normalize_text("T UNG CHO HOANG ANH") == "TAM UNG CHO HOANG ANH"


def test_parse_amount_common_formats():
    assert parse_amount("1,234,567.00") == 1234567
    assert parse_amount("1.234.567") == 1234567
    assert parse_amount("") == 0


def test_parse_date_string_with_time():
    assert parse_date("01/04/2026 11:40:57") == date(2026, 4, 1)
