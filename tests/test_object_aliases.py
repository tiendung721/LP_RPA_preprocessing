from src.object_aliases import load_object_aliases


def test_loader_does_not_auto_add_short_generic_code_alias(tmp_path):
    alias_file = tmp_path / "aliases.yaml"
    alias_file.write_text(
        """
payable:
  TCT:
    - "TIEN DIEN"
  KBB:
    - "KBB"
receivable: {}
internal:
  DUC:
    - "LE NGOC DUC"
""",
        encoding="utf-8",
    )

    aliases = load_object_aliases(alias_file)

    assert aliases["payable"]["TCT"] == ["TIEN DIEN"]
    assert aliases["payable"]["KBB"] == ["KBB"]
    assert aliases["internal"]["DUC"] == ["LE NGOC DUC"]
