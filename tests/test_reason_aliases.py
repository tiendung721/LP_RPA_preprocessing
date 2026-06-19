from src.reason_aliases import load_reason_purposes, match_reason_purpose


def test_reason_purpose_loader_blocks_generic_aliases_and_matches_longest(tmp_path):
    alias_file = tmp_path / "reason_aliases.yaml"
    alias_file.write_text(
        """
purposes:
  - code: electricity
    label: "tiền điện"
    aliases:
      - "TIEN DIEN"
      - "TT"
  - code: utilities
    label: "tiền điện nước"
    aliases:
      - "TIEN DIEN NUOC"
""",
        encoding="utf-8",
    )

    purposes = load_reason_purposes(alias_file)

    assert purposes[0].aliases == ("TIEN DIEN",)
    assert match_reason_purpose("TT TIEN DIEN NUOC THANG 3", purposes).code == "utilities"
    assert match_reason_purpose("TT ABC", purposes) is None


def test_reason_purpose_loader_falls_back_to_empty_for_missing_file(tmp_path):
    assert load_reason_purposes(tmp_path / "missing.yaml") == []
