"""Tests for :func:`slugify.slugify` and its command line front end.

Run with ``make test`` or ``python3 -m unittest discover -s tests -t .``
"""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slugify import slugify  # noqa: E402

CLI = [sys.executable, str(ROOT / "slugify.py")]

#: The output alphabet. Digits and the hyphen are the only legal characters.
OUTPUT_SHAPE = re.compile(r"\A[a-z0-9-]*\Z")


class SlugShape(unittest.TestCase):
    """Invariants that must hold for *any* input."""

    #: Awkward inputs: punctuation, whitespace kinds, scripts we cannot map.
    HOSTILE_INPUTS = [
        "",
        " ",
        "\t\n\r",
        "!!!",
        "---",
        "Привет, мир!",
        "café",
        "Ærø Straße",
        "中文字幕",
        "😀 emoji 🎉 party",
        "١٢٣",
        "ＦＵＬＬＷＩＤＴＨ",
        "Ünicode İstanbul",
        "a" * 5000,
        "slug-уже-готово",
    ]

    def test_output_alphabet_is_ascii_lowercase_digits_and_hyphen(self):
        for text in self.HOSTILE_INPUTS:
            with self.subTest(text=text[:30]):
                self.assertRegex(slugify(text), OUTPUT_SHAPE)

    def test_never_leaves_a_hyphen_on_an_edge(self):
        for text in self.HOSTILE_INPUTS:
            with self.subTest(text=text[:30]):
                out = slugify(text)
                self.assertFalse(out.startswith("-"), out)
                self.assertFalse(out.endswith("-"), out)

    def test_never_produces_two_hyphens_in_a_row(self):
        for text in self.HOSTILE_INPUTS:
            with self.subTest(text=text[:30]):
                self.assertNotIn("--", slugify(text))

    def test_is_idempotent(self):
        """Slugifying a slug must be a no-op -- it is already ASCII safe."""
        for text in self.HOSTILE_INPUTS:
            with self.subTest(text=text[:30]):
                once = slugify(text)
                self.assertEqual(once, slugify(once))


class EmptyAndBlank(unittest.TestCase):
    def test_empty_string_gives_empty_string(self):
        self.assertEqual(slugify(""), "")

    def test_whitespace_only_gives_empty_string(self):
        for text in (" ", "   ", "\t", "\n", "\r\n", " \t\n "):
            with self.subTest(text=text):
                self.assertEqual(slugify(text), "")

    def test_punctuation_only_gives_empty_string(self):
        for text in ("!", "!!!", "?!.,;", "-", "--", "---", "«»", "…"):
            with self.subTest(text=text):
                self.assertEqual(slugify(text), "")

    def test_unmappable_script_only_gives_empty_string(self):
        for text in ("中文字幕", "😀", "١٢٣"):
            with self.subTest(text=text):
                self.assertEqual(slugify(text), "")


class CaseFolding(unittest.TestCase):
    def test_lowercases_latin(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_lowercases_cyrillic(self):
        self.assertEqual(slugify("ПРИВЕТ"), "privet")

    def test_lowercases_before_transliterating(self):
        """É must fold to a Latin e, never to a Cyrillic е."""
        self.assertEqual(slugify("ÉTÉ"), "ete")
        self.assertTrue(slugify("ÉTÉ").isascii())


class Transliteration(unittest.TestCase):
    def test_russian(self):
        cases = {
            "Привет, мир!": "privet-mir",
            "Это URL-slug из кириллицы": "eto-url-slug-iz-kirillitsy",
            "ёлка": "elka",
            "хлеб": "khleb",
            "цапля": "tsaplya",
            "чаща": "chashcha",
            "щи": "shchi",
            "юла": "yula",
            "яма": "yama",
            "объект": "obekt",  # hard sign is unpronounced
            "ь": "",  # soft sign alone carries nothing
            "москва": "moskva",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(slugify(text), expected)

    def test_short_i_follows_iso9_not_unidecode(self):
        """й is y, not i.

        ISO 9 and BGN give y (mayon, kray, chay). Django's Unidecode gives i
        (maion, krai, chai), which reads worse in a URL. Pinned deliberately so
        that a well-meaning 'match Unidecode' change has to be argued for.
        """
        cases = {"Майон": "mayon", "Край": "kray", "Чай": "chay", "Мой": "moy"}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(slugify(text), expected)

    def test_ukrainian_is_best_effort(self):
        """Ukrainian approximates; see the README limitations section.

        ї must survive as yi. It does not if NFKD runs before transliteration,
        because NFKD splits ї into і + combining diaeresis and the combining
        mark is then discarded.
        """
        cases = {
            "Українська": "ukrayinska",  # ї -> yi, correct
            "Їжак": "yizhak",  # leading ї
            "Київ": "kiyiv",  # official KMU 2023 wants kyiv; needs и -> y
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(slugify(text), expected)

    def test_belarusian_short_u_survives(self):
        """ў is u. NFKD would split it into у + combining breve first."""
        self.assertEqual(slugify("ў"), "u")

    def test_every_table_entry_is_actually_reachable(self):
        """Regression: no CYRILLIC key may be silently bypassed.

        Four keys (ё, й, ї, ў) carry a diacritic that NFKD decomposes into a
        base letter plus a combining mark. Any pipeline that normalises before
        transliterating drops the mark first, so those keys never get looked up
        and the table quietly disagrees with the code. Asserting each letter
        alone maps to its own table value makes that failure loud.
        """
        from translit import CYRILLIC

        for letter, value in CYRILLIC.items():
            with self.subTest(letter=letter):
                self.assertEqual(slugify(letter), value.strip("-"))

    def test_table_values_survive_normalisation(self):
        """Whatever transliteration emits must be stable under NFKD.

        A value that NFKD would decompose would get folded by the very next
        step, so the table would not describe the output.
        """
        from translit import CYRILLIC, LIGATURES

        for letter, value in list(CYRILLIC.items()) + list(LIGATURES.items()):
            with self.subTest(letter=letter):
                self.assertEqual(
                    unicodedata.normalize("NFKD", value), value, value
                )

    def test_tables_do_not_overlap(self):
        """Static-data invariant, also asserted at import in slugify.py.

        The module-level assert is stripped under ``python -O``, so the check is
        repeated here where it holds regardless of how the suite is run. If a
        character ever lands in both tables, the result would depend on step
        order rather than on intent.
        """
        from translit import CYRILLIC, LIGATURES

        self.assertEqual(CYRILLIC.keys() & LIGATURES.keys(), set())

    def test_table_keys_are_lowercase(self):
        """slugify() lowercases before lookup, so the tables must be lowercase."""
        from translit import CYRILLIC, LIGATURES

        for letter in list(CYRILLIC) + list(LIGATURES):
            with self.subTest(letter=letter):
                self.assertEqual(letter, letter.lower())

    def test_uppercase_cyrillic_is_not_lost(self):
        """Regression for the tables being lowercase-only.

        Without an early str.lower(), uppercase Cyrillic misses the table and is
        destroyed by the separator pass: ПРИВЕТ -> '' and Привет -> 'rivet'.
        """
        self.assertEqual(slugify("ПРИВЕТ"), "privet")
        self.assertEqual(slugify("Привет"), "privet")
        self.assertEqual(slugify("ПРИВЕТ МИР"), "privet-mir")

    def test_accented_capitals_survive(self):
        """É must be lowercased before NFKD, or it becomes a hyphen."""
        self.assertEqual(slugify("ÉTÉ"), "ete")
        self.assertEqual(slugify("CAFÉ"), "cafe")

    def test_soft_and_hard_signs_stay_in_the_table(self):
        """They must map to "" rather than be deleted.

        An unmapped character is not dropped -- it survives to the separator
        pass and becomes a hyphen. Deleting these keys would give pal-to.
        """
        from translit import CYRILLIC

        self.assertEqual(CYRILLIC["ь"], "")
        self.assertEqual(CYRILLIC["ъ"], "")
        self.assertEqual(slugify("пальто"), "palto")
        self.assertEqual(slugify("съезд"), "sezd")
        self.assertEqual(slugify("объект"), "obekt")
        self.assertEqual(slugify("ь"), "")

    def test_table_covers_the_whole_alphabet(self):
        from translit import CYRILLIC

        expected = set(
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"  # Russian
            "іїєґ"  # Ukrainian
            "ў"  # Belarusian
            "ђјљњћџ"  # Serbian
        )
        self.assertEqual(expected - set(CYRILLIC), set())

    def test_serbian(self):
        self.assertEqual(slugify("љер"), "ljer")


class DiacriticsAndLigatures(unittest.TestCase):
    def test_accented_latin_is_folded(self):
        self.assertEqual(slugify("café"), "cafe")
        self.assertEqual(slugify("Àéîõü"), "aeiou")

    def test_letters_nfkd_cannot_decompose_are_mapped(self):
        cases = {
            "Ærø": "aero",
            "Straße": "strasse",
            "łódź": "lodz",
            "Ðór": "dor",
            "þorn": "thorn",
            "Œuvre": "oeuvre",
            "ı": "i",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(slugify(text), expected)

    def test_combining_marks_alone_are_dropped(self):
        # "e" plus a standalone combining acute.
        self.assertEqual(slugify("café"), "cafe")


class Separators(unittest.TestCase):
    def test_spaces_become_hyphens(self):
        self.assertEqual(slugify("hello world"), "hello-world")

    def test_repeated_whitespace_collapses_to_one_hyphen(self):
        self.assertEqual(slugify("a   b"), "a-b")
        self.assertEqual(slugify("a\t\t\tb"), "a-b")

    def test_punctuation_becomes_hyphens(self):
        self.assertEqual(slugify("hello, world!"), "hello-world")

    def test_mixed_punctuation_collapses(self):
        self.assertEqual(slugify("a!!!???b"), "a-b")

    def test_repeated_hyphens_collapse(self):
        self.assertEqual(slugify("a--b"), "a-b")
        self.assertEqual(slugify("a----b"), "a-b")

    def test_newlines_become_hyphens(self):
        self.assertEqual(slugify("a\nb"), "a-b")

    def test_edge_hyphens_are_stripped(self):
        self.assertEqual(slugify("--hello--"), "hello")
        self.assertEqual(slugify("---"), "")
        self.assertEqual(slugify("- leading"), "leading")
        self.assertEqual(slugify("trailing -"), "trailing")

    def test_surrounding_whitespace_and_punctuation_are_stripped(self):
        self.assertEqual(slugify("  --Hello__World--  "), "hello-world")

    def test_digits_are_kept(self):
        self.assertEqual(slugify("Версия 2 point 0"), "versiya-2-point-0")

    def test_digits_from_other_scripts_do_not_leak(self):
        """Arabic-Indic digits are digits to str.isalnum but not to us."""
        for text in ("\u0662\u0663", "\uff12\uff13"):
            with self.subTest(text=text):
                out = slugify(text)
                self.assertNotIn("\u0662", out)
                self.assertRegex(out, OUTPUT_SHAPE)


class CommandLine(unittest.TestCase):
    """Exercise the real binary so argv/stdin behaviour is actually covered."""

    def run_cli(self, *args: str, stdin: str = "") -> str:
        proc = subprocess.run(
            [*CLI, *args], input=stdin, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_single_argument(self):
        self.assertEqual(self.run_cli("Hello World"), "hello-world\n")

    def test_several_arguments_are_joined_with_spaces(self):
        self.assertEqual(self.run_cli("Hello", "World"), "hello-world\n")

    def test_cyrillic_argument(self):
        self.assertEqual(self.run_cli("Привет, мир!"), "privet-mir\n")

    def test_reads_stdin_when_no_arguments(self):
        self.assertEqual(self.run_cli(stdin="Hello World"), "hello-world\n")

    def test_reads_cyrillic_stdin(self):
        self.assertEqual(self.run_cli(stdin="Привет, мир!"), "privet-mir\n")

    def test_empty_stdin_prints_nothing(self):
        """Empty in, empty out: zero bytes, not a blank line.

        A stray newline here would end up inside a URL path or a filename.
        """
        self.assertEqual(self.run_cli(stdin=""), "")

    def test_empty_argument_prints_nothing(self):
        self.assertEqual(self.run_cli(""), "")

    def test_punctuation_only_argument_prints_nothing(self):
        self.assertEqual(self.run_cli("!!!"), "")

    def test_unmappable_input_prints_nothing(self):
        self.assertEqual(self.run_cli("中文字幕"), "")

    def test_empty_input_still_exits_zero(self):
        proc = subprocess.run([*CLI], input="", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")

    def test_non_empty_output_ends_with_exactly_one_newline(self):
        out = self.run_cli("Hello World")
        self.assertEqual(out, "hello-world\n")
        self.assertFalse(out.endswith("\n\n"))

    def test_whitespace_only_stdin_is_trimmed_not_kept(self):
        self.assertEqual(self.run_cli(stdin="  hello  \n"), "hello\n")

    def test_stdin_is_not_read_when_arguments_are_given(self):
        """argv wins; stdin is ignored rather than appended."""
        out = self.run_cli("Given", stdin="Ignored")
        self.assertEqual(out, "given\n")

    def test_multiline_stdin_becomes_one_slug(self):
        self.assertEqual(self.run_cli(stdin="first line\nsecond line"), "first-line-second-line\n")

    def test_help_exits_zero_and_mentions_usage(self):
        proc = subprocess.run([*CLI, "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage", proc.stdout.lower())

    def test_short_help_flag(self):
        proc = subprocess.run([*CLI, "-h"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage", proc.stdout.lower())


class LeadingDashes(unittest.TestCase):
    """A leading dash is content, not a flag.

    Hyphens are what this tool emits, so `slugify '---'` is an ordinary call.
    argparse cannot express "a positional that may begin with a dash" and would
    reject it with exit 2. -h/--help are the only flags, so anything else
    starting with a dash is text.
    """

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([*CLI, *args], capture_output=True, text=True)

    def test_hyphens_only_is_empty_not_an_error(self):
        proc = self.run_cli("---")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_leading_hyphen_with_text(self):
        self.assertEqual(self.run_cli("-tagged").stdout, "tagged\n")

    def test_unknown_looking_flag_is_text(self):
        proc = self.run_cli("--nope")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "nope\n")

    def test_single_hyphen_is_empty(self):
        self.assertEqual(self.run_cli("-").stdout, "")

    def test_double_dash_marker_still_separates_options(self):
        """`slugify -- -h` slugifies -h rather than printing help."""
        proc = self.run_cli("--", "-h")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "h\n")

    def test_no_usage_noise_on_stderr(self):
        """Text that looks like a flag must not print a usage error."""
        for arg in ("---", "--nope", "-tagged"):
            with self.subTest(arg=arg):
                self.assertEqual(self.run_cli(arg).stderr, "")

    def test_help_still_wins_at_position_zero(self):
        self.assertIn("usage", self.run_cli("-h").stdout.lower())
        self.assertIn("usage", self.run_cli("--help").stdout.lower())

    def test_help_is_recognised_after_text_too(self):
        """--help is unambiguous, so argparse handles it in the normal path."""
        proc = self.run_cli("text", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage", proc.stdout.lower())

    def test_flag_after_real_text_is_still_an_error(self):
        """Only the first argument is ambiguous; after text a flag is a flag."""
        proc = self.run_cli("Hello", "--nope")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
