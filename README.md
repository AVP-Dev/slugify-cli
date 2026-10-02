# slugify

Turn text into a lowercase ASCII URL slug. Latin is lowercased, Cyrillic is
transliterated, and everything else becomes hyphens.

```console
$ slugify 'Привет, мир!'
privet-mir

$ slugify '  --Hello__World--  '
hello-world

$ echo 'Café Ærø Straße' | slugify
cafe-aero-strasse
```

No dependencies, no install step, Python 3.9+.

## Usage

```console
slugify [TEXT...]
```

Text comes from the command line, or from stdin when no argument is given.
Several arguments are joined with single spaces.

```console
$ slugify Hello World          # arguments
hello-world

$ echo 'Hello World' | slugify # stdin
hello-world

$ printf 'one\ntwo\n' | xargs slugify   # one slug per line
one
two
```

| Option | Meaning |
| --- | --- |
| `-h`, `--help` | Show usage and exit |

Those are the only options. Anything else starting with a dash is treated as
**text**, because hyphens are what this tool emits:

```console
$ slugify '---'          # empty slug, not a usage error
$ slugify '-tagged'      # tagged
$ slugify --nope         # nope
$ slugify -- -h          # h  (-- still separates options)
```

Only the *first* argument is ambiguous. After real text, a leading dash is a
genuine flag attempt and stays an error: `slugify Hello --nope` exits `2`.

## What it does

Given any input, `slugify` guarantees an output matching `[a-z0-9-]*`, and:

1. **Latin is lowercased.** `Hello World` → `hello-world`.
2. **Cyrillic is transliterated.** `Привет` → `privet`, `хлеб` → `khleb`.
3. **Diacritics are dropped.** `café` → `cafe`, `Łódź` → `lodz`.
4. **Letters NFKD cannot split are folded.** `Ærø` → `aero`, `Straße` → `strasse`.
5. **Spaces and punctuation become hyphens.** `a, b!c` → `a-b-c`.
6. **Repeated hyphens collapse to one.** `a--b` → `a-b`.
7. **Hyphens at either edge are removed.** `--hello--` → `hello`.
8. **Empty input gives empty output.**

### Empty output means zero bytes

An empty slug writes **nothing at all**, not a blank line:

```console
$ slugify '' | wc -c
0
$ slugify '!!!' | wc -c        # nothing survives to be a slug
0
$ slugify '---' | wc -c
0
```

A non-empty slug is newline-terminated, so interactive use still returns your
shell prompt. The reason empty output is silent: this tool's job is to hand a
slug to something else — a URL path, a filename, a database column — and a
stray newline travelling into those places is a bug the caller has to strip.
`slugify` exits `0` in this case; it is a legitimate result, not an error.

## Transliteration

One flat table covers Russian, Ukrainian, Belarusian and the common Serbian
letters. Notable choices:

| Cyrillic | Latin | Note |
| --- | --- | --- |
| `й` | `y` | ISO 9 / BGN. `Майон` → `mayon`. Unidecode gives `maion`. |
| `х` | `kh` | Not `h`. `хлеб` → `khleb`. |
| `ц` | `ts` | `цапля` → `tsaplya`. |
| `ч` | `ch` | `чаща` → `chashcha`. |
| `ш` | `sh` | |
| `щ` | `shch` | |
| `ю` | `yu` | `юла` → `yula`. |
| `я` | `ya` | `яма` → `yama`. |
| `ё` | `e` | Not `yo`. `ёлка` → `elka`. |
| `ъ`, `ь` | *(dropped)* | Unpronounced, so they carry nothing. `объект` → `obekt`. |
| `ї` | `yi` | |
| `є` | `ie` | |
| `ў` | `u` | Belarusian short u. |

### Known limitations

- **Ukrainian is approximate.** A single table cannot romanise two languages
  correctly. Ukrainian officially maps `и` to `y` (KMU 2023), but doing that
  here would turn Russian `мир` into `myr`. Russian wins, because it dominates
  Cyrillic slugs. The cost: `Київ` → `kiyiv`, not `kyiv`. A dedicated
  Ukrainian scheme would need a separate table.
- **Greek, CJK, emoji and other scripts are dropped**, not transliterated.
  `中文字幕` produces an empty slug.
- **Digits from other scripts are dropped.** Arabic-Indic `٢٣` is dropped
  rather than becoming `23`; fullwidth `２３` becomes `23`, because NFKD folds
  fullwidth forms onto ASCII.
- **Transliteration is not reversible.** `sluga` and `слуга` both give `sluga`.
  Slugs are for identity in a URL, not for recovering the original text. If you
  need round-tripping, store the original alongside the slug.

## How it works

Five ordered steps, in `slugify.py`:

1. `str.lower()` — fold case while the text is still recognisable letters.
2. Fold Latin letters NFKD will not decompose (`ø`, `ß`, `ł`, `þ`, …).
3. Transliterate Cyrillic.
4. NFKD-normalise, then discard combining marks.
5. Map every run outside `[a-z0-9]` to one hyphen, then strip edge hyphens.

**Step 3 must precede step 4.** NFKD decomposes Cyrillic letters carrying a
diacritic — `й` becomes `и` + U+0306, `ё` becomes `е` + U+0308, `ї` becomes `і` +
U+0308, `ў` becomes `у` + U+0306. Since step 4 discards combining marks,
normalising first makes four of the 44 table entries unreachable: `ї` would
transliterate as `i` instead of `yi`. Transliterating first removes all Cyrillic
before the marks are dropped, so step 4 only ever folds Latin diacritics — which
is what it is good at.

Both tables are applied with `str.translate`, so each walks the string once
rather than re-scanning it per entry.

Digits are kept only in ASCII form. `str.isalnum()` is deliberately not used as
the filter: it accepts `Ж`, `Ü`, fullwidth digits and Arabic-Indic digits, all of
which would leak into a slug.

## Development

```console
make test    # 56 tests
make demo    # pipe a sample through the CLI
```

Or directly:

```console
python3 -m unittest discover -s tests -t . -v
python3 -m doctest slugify.py -v
```

The suite covers the core function and drives the real binary over a pipe, so
the argv/stdin contract and the byte-exact empty-output behaviour are actually
exercised rather than assumed.

Two tests exist to catch a specific historical bug and are worth knowing about
before editing step order:

- `test_every_table_entry_is_actually_reachable` transliterates each Cyrillic
  letter on its own and compares it to that letter's own table entry.
- `test_table_values_survive_normalisation` asserts no table output would itself
  be decomposed by NFKD.

Reintroducing the wrong order fails 9 tests.
