from __future__ import annotations

import unicodedata
from typing import Any


# TCVN3/VSCII-3 uses normal uppercase glyphs only for base Vietnamese letters.
# Tone-bearing uppercase vowels are mapped to the normal-font lowercase code.
_TCVN3_BASE_MAP = {
    "Ă": "¡",
    "Â": "¢",
    "Ê": "£",
    "Ô": "¤",
    "Ơ": "¥",
    "Ư": "¦",
    "Đ": "§",
    "ă": "¨",
    "â": "©",
    "ê": "ª",
    "ô": "«",
    "ơ": "¬",
    "ư": "\u00ad",
    "đ": "®",
}

_TCVN3_LOWER_TONE_MAP = {
    "à": "µ",
    "ả": "¶",
    "ã": "·",
    "á": "¸",
    "ạ": "¹",
    "ằ": "»",
    "ẳ": "¼",
    "ẵ": "½",
    "ắ": "¾",
    "ặ": "Æ",
    "ầ": "Ç",
    "ẩ": "È",
    "ẫ": "É",
    "ấ": "Ê",
    "ậ": "Ë",
    "è": "Ì",
    "ẻ": "Î",
    "ẽ": "Ï",
    "é": "Ð",
    "ẹ": "Ñ",
    "ề": "Ò",
    "ể": "Ó",
    "ễ": "Ô",
    "ế": "Õ",
    "ệ": "Ö",
    "ì": "×",
    "ỉ": "Ø",
    "ĩ": "Ü",
    "í": "Ý",
    "ị": "Þ",
    "ò": "ß",
    "ỏ": "á",
    "õ": "â",
    "ó": "ã",
    "ọ": "ä",
    "ồ": "å",
    "ổ": "æ",
    "ỗ": "ç",
    "ố": "è",
    "ộ": "é",
    "ờ": "ê",
    "ở": "ë",
    "ỡ": "ì",
    "ớ": "í",
    "ợ": "î",
    "ù": "ï",
    "ủ": "ñ",
    "ũ": "ò",
    "ú": "ó",
    "ụ": "ô",
    "ừ": "õ",
    "ử": "ö",
    "ữ": "÷",
    "ứ": "ø",
    "ự": "ù",
    "ỳ": "ú",
    "ỷ": "û",
    "ỹ": "ü",
    "ý": "ý",
    "ỵ": "þ",
}

_TCVN3_UPPER_TONE_FALLBACK_MAP = {
    letter.upper(): encoded
    for letter, encoded in _TCVN3_LOWER_TONE_MAP.items()
}

_UNICODE_TO_TCVN3 = str.maketrans(
    {
        **_TCVN3_BASE_MAP,
        **_TCVN3_LOWER_TONE_MAP,
        **_TCVN3_UPPER_TONE_FALLBACK_MAP,
    }
)


def unicode_to_tcvn3(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    return text.translate(_UNICODE_TO_TCVN3)
