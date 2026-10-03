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

Lowercasing comes first because every key in both tables is lowercase, so
uppercase input would otherwise miss the tables entirely and be destroyed by
step 5: ``ПРИВЕТ`` would slug to ``""`` and ``Привет`` to ``rivet``, the ``П``
being eaten. It also matters for accented capitals: ``É`` must become ``é``
before step 4 so that NFKD splits it into ``e`` plus a combining acute, rather
than into ``E``, which is not in ``[a-z0-9]`` and would become a hyphen.

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

# Static-data invariant: if a character ever appears in both tables, the outcome
# would depend on step order rather than on intent. Also asserted by the test
# suite, since python -O strips this.
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

    # 2. Latin letters NFKD leaves alone. Their position relative to step 4 is
    #    irrelevant -- NFKD cannot touch what it does not decompose -- but they
    #    must land before step 5, which would otherwise flatten ø into a hyphen.
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


#: The only flags this tool has.
_HELP_FLAGS = frozenset({"-h", "--help"})


def _wants_help(argv: list[str]) -> bool:
    """True when the arguments ask for help before any text is seen.

    This is the one flag decision that must be made before parsing, because the
    other branch hands the whole argv to the slugifier as text. Later arguments
    need no special case: argparse still recognises ``--help`` in the ordinary
    path, so ``slugify text --help`` prints help too.
    """
    return bool(argv) and argv[0] in _HELP_FLAGS


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
            "  slugify '!!!'                -> prints nothing (empty slug)\n"
            "\n"
            "-h/--help is the only option. Any other argument starting with a\n"
            "dash is treated as text, so 'slugify ---' is valid."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="text to slugify; several arguments are joined with single spaces",
    )

    if argv is None:
        argv = sys.argv[1:]

    if _wants_help(argv):
        parser.print_help()
        return 0

    if argv and argv[0].startswith("-") and argv[0] != "--":
        # argparse cannot express "a positional that may begin with a dash", and
        # for this tool a leading dash is far more likely to be content than an
        # option: hyphens are what it emits, so `slugify '---'` and `slugify
        # '-tagged'` are ordinary calls. Since -h/--help are the only flags,
        # anything else starting with a dash is text.
        #
        # Decided here, before parsing, so argparse never prints a usage error
        # we are about to ignore. Only the first argument is ambiguous; after
        # real text a leading dash is a genuine flag attempt and stays an error.
        words = argv
    else:
        # Handles "--" itself, and still reports unknown flags after text.
        words = parser.parse_args(argv).text

    if words:
        source = " ".join(words)
    else:
        source = sys.stdin.read()

    result = slugify(source)
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
