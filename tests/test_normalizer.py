from datetime import date

from src.normalizer import normalize_text, parse_amount, parse_date


def test_normalize_vietnamese_text():
    assert normalize_text("Nộp thuế GTGT tháng 03/2026") == "NOP THUE GTGT THANG 03 2026"


def test_parse_amount_common_formats():
    assert parse_amount("1,234,567.00") == 1234567
    assert parse_amount("1.234.567") == 1234567
    assert parse_amount("") == 0


def test_parse_date_string_with_time():
    assert parse_date("01/04/2026 11:40:57") == date(2026, 4, 1)
