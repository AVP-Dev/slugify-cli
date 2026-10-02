"""Transliteration tables for :mod:`slugify`.

Two dictionaries live here:

``CYRILLIC``
    Cyrillic letters (Russian, Ukrainian, Belarusian, plus the common
    Serbian/Macedonian extras) mapped to the Latin spelling used by most URL
    slug generators.

    Soft sign and hard sign map to the empty string *on purpose, and must stay
    in the table*. They are unpronounced, so they belong in no slug -- but
    deleting the keys would be a bug, not a cleanup: an unmapped character is
    not dropped, it survives until the separator pass and becomes a hyphen.
    ``пальто`` would become ``pal-to`` and ``объект`` ``ob-ekt``. Mapping them
    to ``""`` removes them; omitting them does not.

    Every key here is lowercase, which is why :func:`slugify.slugify` lowercases
    its input before looking anything up.

``LIGATURES``
    Latin letters that NFKD does *not* decompose. These must be folded *before*
    normalisation runs, otherwise they survive as stray characters and get
    flattened into a hyphen by the separator pass (``Aø`` would become ``a-``
    instead of ``ao``).
"""

from __future__ import annotations

#: Cyrillic -> Latin, following the practical ISO 9 / BGN web-slug convention
#: (``х`` -> ``kh``, ``щ`` -> ``shch``, ``й`` -> ``y``).
#:
#: Kept as explicit pairs rather than a ``str.translate`` table so that every
#: letter is visible in one place and easy to audit for typos.
#:
#: One flat table cannot be right for two languages at once. Russian wins here
#: because it dominates Cyrillic slugs, and it is what fixes ``й``: ISO 9 gives
#: ``y`` (``mayon``, ``kray``, ``chay``) where Django/Unidecode gives ``i``
#: (``maion``, ``krai``, ``chai``). The cost is Ukrainian, whose official KMU
#: 2023 romanisation also maps ``и`` to ``y``; doing that here would turn
#: Russian ``мир`` into ``myr``, so ``Київ`` comes out as ``kiyiv``, not
#: ``kyiv``. See the README's limitations section.
CYRILLIC: dict[str, str] = {
    # Russian
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # Ukrainian
    "і": "i",
    "ї": "yi",
    "є": "ie",
    "ґ": "g",
    # Belarusian
    "ў": "u",
    # Serbian / Macedonian, cheap to include and common in slugs
    "ђ": "dj",
    "ј": "j",
    "љ": "lj",
    "њ": "nj",
    "ћ": "c",
    "џ": "dz",
}

#: Latin letters that survive NFKD unchanged and so need an explicit mapping.
LIGATURES: dict[str, str] = {
    "ø": "o",   # ø
    "œ": "oe",  # œ
    "æ": "ae",  # æ
    "ß": "ss",  # ß
    "đ": "d",   # đ
    "ð": "d",   # ð
    "þ": "th",  # þ
    "ł": "l",   # ł
    "ħ": "h",   # ħ
    "ı": "i",   # ı
    "ŋ": "ng",  # ŋ
    "ƒ": "f",   # ƒ
}
