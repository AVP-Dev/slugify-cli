"""Turn arbitrary text into a URL slug.

The pipeline is five ordered steps, and step 3 must precede step 4:

1. :func:`str.lower` -- fold case while the text is still recognisable letters.
2. :data:`translit.LIGATURES` -- fold the Latin letters NFKD will not decompose.
3. :data:`translit.CYRILLIC` -- transliterate Cyrillic to Latin.
4. NFKD + drop combining marks -- turns ``é`` into ``e`` without a table.
5. Replace every run outside ``[a-z0-9]`` with one ``-``, then strip edge hyphens.

Step order is not cosmetic. NFKD decomposes Cyrillic letters that carry a
diacritic: ``й`` becomes ``и`` + U+0306, ``ё`` becomes ``е`` + U+0308, ``ї``
becomes ``і`` + U+0308, ``ў`` becomes ``у`` + U+0306. Step 4 discards combining
marks, so running it first quietly erases the breve and those four table entries
become unreachable -- ``ї`` would transliterate as ``i`` instead of ``yi``.
Transliterating first removes all Cyrillic from the string, leaving step 4 with
nothing but Latin diacritics to fold, which is what it is good at.

Lowercasing comes first for the same reason: ``É`` must reach step 4 as ``É`` so
that NFKD splits it into ``E`` plus a combining acute, rather than arriving at
step 3 as something needing transliteration.

Step 5 handles "collapse repeated hyphens" and "strip edge hyphens" at once,
because the ``+`` quantifier turns every run of separators into exactly one
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

    # 2. Latin letters NFKD leaves alone. Must precede step 4, since ø is no
    #    more decomposable after normalisation than before it.
    text = text.translate(_LIGATURE_MAP)

    # 3. Cyrillic to Latin, while its diacritics are still intact. See the
    #    module docstring: running step 4 first makes four of these entries
    #    unreachable.
    text = text.translate(_CYRILLIC_MAP)

    # 4. Whatever Latin diacritics remain, folded away for free: decompose,
    #    then drop the combining marks. Safe now because step 3 left no
    #    Cyrillic behind, and every table value is plain ASCII.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    # 5. Every remaining run of non-alphanumerics becomes one hyphen...
    text = _SEPARATORS.sub("-", text)
    #    ...and none may touch an edge.
    return text.strip("-")


def main(argv: list[str] | None = None) -> int:
    """Read text from ``argv`` or stdin and print the slug. Return exit code.

    An empty slug prints nothing at all -- zero bytes, not a blank line. The
    point of this tool is to hand a slug to something else (a URL path, a
    filename, a database column), and a stray newline in those places is a bug
    the caller has to strip. Non-empty slugs are newline-terminated so the tool
    still behaves like a normal command when run interactively.
    """
    parser = argparse.ArgumentParser(
        prog="slugify",
        description="Turn text into a lowercase ASCII URL slug.",
        epilog=(
            "With no ARGUMENTS, reads stdin instead. Examples:\n"
            "  slugify 'Привет, мир!'      -> privet-mir\n"
            "  echo 'Hello World' | slugify -> hello-world\n"
            "  slugify '!!!'                -> prints nothing (empty slug)"
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

    result = slugify(source)
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
