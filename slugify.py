"""Turn arbitrary text into a URL slug.

The pipeline is deliberately explicit, and the order of the first three steps
is load-bearing:

1. :func:`str.lower` -- fold case while the text is still recognisable letters.
2. :data:`translit.LIGATURES` -- fold the Latin letters NFKD will not decompose.
3. NFKD + drop combining marks -- turns ``é`` into ``e`` without a table.
4. :data:`translit.CYRILLIC` -- transliterate Cyrillic to Latin.
5. Replace every run outside ``[a-z0-9]`` with a single ``-``, then strip the
   hyphens touching either edge.

Why lowercasing comes first: ``É`` must reach step 3 as ``É`` so that NFKD
decomposes it into ``E`` + combining acute, rather than arriving at step 4 as a
Cyrillic-looking letter that needs transliterating.

Steps 5 handles both "collapse repeated hyphens" and "strip edge hyphens" at
once, because the ``+`` quantifier makes every run of separators exactly one
hyphen and ``strip("-")`` removes the ends. Nothing after step 5 can introduce a
hyphen, so a second collapse pass would be unreachable code.

Empty input yields empty output; every step is a no-op on ``""``.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata

from translit import CYRILLIC, LIGATURES

__all__ = ["slugify", "main"]

#: Static-data invariant: if a character ever appears in both tables, the
#: outcome would depend on step order rather than on intent.
assert not (CYRILLIC.keys() & LIGATURES.keys()), "translit tables overlap"

#: Anything outside this set is a separator. An explicit ASCII whitelist rather
#: than ``str.isalnum()``, which accepts ``Ж``, ``Ü`` and fullwidth or
#: Arabic-Indic digits -- all of which would otherwise leak into a slug.
_SEPARATORS = re.compile(r"[^a-z0-9]+")

# Built once at import: str.translate walks the string a single time, where a
# loop of str.replace would re-scan it once per table entry.
_LIGATURE_MAP = str.maketrans(LIGATURES)
_CYRILLIC_MAP = str.maketrans(CYRILLIC)


def slugify(text: str) -> str:
    """Return ``text`` as a lowercase ASCII slug.

    >>> slugify("Привет, мир!")
    'privet-mir'
    >>> slugify("  --Hello__World--  ")
    'hello-world'
    >>> slugify("")
    ''
    """
    # 1. Case folding, while the text is still recognisable as letters.
    text = text.lower()

    # 2. Latin letters NFKD leaves alone -- must run before step 3, because
    #    after it ø is no more decomposed than it was before.
    text = text.translate(_LIGATURE_MAP)

    # 3. Diacritics for free: decompose, then drop the combining marks.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    # 4. Cyrillic to Latin. Cyrillic is stable under NFKD, so deferring it
    #    until after step 3 costs nothing.
    text = text.translate(_CYRILLIC_MAP)

    # 5. Every remaining run of non-alphanumerics becomes one hyphen...
    text = _SEPARATORS.sub("-", text)
    #    ...and none may touch an edge.
    return text.strip("-")


def main(argv: list[str] | None = None) -> int:
    """Read text from ``argv`` or stdin, print one slug line. Return exit code.

    Always prints exactly one newline-terminated line, so the tool composes with
    ``xargs``, ``while read`` and friends. Empty input therefore yields a single
    empty line rather than no output at all.
    """
    parser = argparse.ArgumentParser(
        prog="slugify",
        description="Turn text into a lowercase ASCII URL slug.",
        epilog=(
            "With no ARGUMENTS, reads stdin instead. Examples:\n"
            "  slugify 'Привет, мир!'      -> privet-mir\n"
            "  echo 'Hello World' | slugify -> hello-world"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="text to slugify; several arguments are joined with single spaces",
    )
    args = parser.parse_args(argv)

    if args.text:
        source = " ".join(args.text)
    else:
        source = sys.stdin.read()

    print(slugify(source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
