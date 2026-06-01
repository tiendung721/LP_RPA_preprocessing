from src.entity_extractor import OwnCompanyConfig
from src.object_matcher import ObjectMatcher


def test_match_object_by_simplified_name():
    matcher = ObjectMatcher.from_records(
        [{"code": "WANHAI", "name": "Công ty TNHH Wan Hai Việt Nam"}],
        min_score=80,
        min_gap=8,
    )
    result = matcher.match(description="TT CHO WAN HAI BL 040GX03571", counterparty_hint="WAN HAI")
    assert result.status == "OK"
    assert result.code == "WANHAI"


def test_ambiguous_object_match():
    matcher = ObjectMatcher.from_records(
        [
            {"code": "ABC1", "name": "Công ty ABC"},
            {"code": "ABC2", "name": "ABC"},
        ],
        min_score=80,
        min_gap=8,
    )
    result = matcher.match(description="THANH TOAN ABC")
    assert result.status == "AMBIGUOUS"


def test_no_object_match():
    matcher = ObjectMatcher.from_records([{"code": "AAA", "name": "Công ty AAA"}], min_score=80, min_gap=8)
    result = matcher.match(description="THANH TOAN ZZZ")
    assert result.status == "NOT_FOUND"


def test_own_company_candidate_is_excluded():
    own_company = OwnCompanyConfig(["LE PHAM", "CONG TY TNHH LE PHAM"], ["0200410388"], ["LE PHAM"])
    matcher = ObjectMatcher.from_records(
        [
            {"code": "LE PHAM", "name": "Công ty TNHH Lê Phạm"},
            {"code": "PETROLIMEX", "name": "Tổng công ty hóa dầu PETROLIMEX - CTCP"},
        ],
        min_score=80,
        min_gap=8,
        aliases={"PETROLIMEX": ["PETROLIMEX"]},
        own_company=own_company,
    )
    result = matcher.match(
        description="LE PHAM THANH TOAN TIEN XANG DAU CHO PETROLIMEX",
        counterparty_hint="PETROLIMEX",
        cleaned_description="THANH TOAN TIEN XANG DAU CHO PETROLIMEX",
    )
    assert result.status == "OK"
    assert result.code == "PETROLIMEX"
