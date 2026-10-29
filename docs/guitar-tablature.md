# Guitar staff and tablature output

Convert a small, explicit subset of LilyPond melody notation or guitar
string/fret data to staff notation, tablature, or both. These are the two
conversion directions tracked in #8 and #9, part of #4. This is not a general
LilyPond or tablature-file importer.

Requires Python 3.8 or newer, with no external Python packages. LilyPond 2.24.3
or newer is needed to render the generated file, not to run the converter.

## Usage

From the repository root:

```sh
python src/lilypond_transposer/tablature.py \
  tests/fixtures/guitar-open-strings.ly --output guitar.ly --format both
lilypond guitar.ly
```

`--format` accepts `staff`, `tab`, or `both`, defaulting to `both`.
Tab output includes rhythmic notation and visible rests through LilyPond's
`\tabFullNotation`. Staff output uses an octave-down treble clef, as customary
for guitar.

Output files are protected unless `--force` is supplied. The input cannot be
overwritten even with `--force`, including through symlinks or hard links.
The output directory must already exist. Invalid input is rejected before
opening the output file, so it cannot truncate an existing chart.

Use `--help` for options. The existing transposition CLI is unchanged.

## Explicit string/fret input

To convert string/fret positions into standard staff notation:

```sh
python src/lilypond_transposer/tablature.py \
  tests/fixtures/guitar-positions-open.json --input-format positions \
  --format staff --output guitar-staff.ly
lilypond guitar-staff.ly
```

`--input-format` is `lilypond` by default, preserving the existing CLI behavior.
Use `positions` to read the JSON format below. The format is never inferred
from a filename. Output selection is independent: `staff`, `tab`, or `both`.

```json
{
  "version": 1,
  "tuning": "standard",
  "meter": "4/4",
  "measures": [
    [
      {"string": 6, "fret": 0, "duration": "4"},
      {"string": 5, "fret": 2, "duration": "4"},
      {"rest": true, "duration": "2"}
    ]
  ]
}
```

This plays E2 and B2 as quarter notes, then a half-note rest. Each measure is
an array of sequential single-note or rest objects, not a chord or voice.

The version-1 format requires exactly these top-level fields:

| Field | Required value |
| --- | --- |
| `version` | The integer `1` |
| `tuning` | The string `"standard"`, never inferred |
| `meter` | `"2/4"`, `"3/4"`, `"4/4"`, or `"6/8"` |
| `measures` | A nonempty array of nonempty measure arrays |

Each note object requires exactly `string`, `fret`, and `duration`. String
numbers are integers from 1 to 6, with string 1 the highest E4. Frets are
integers from 0 to 20 inclusive. Boolean values and floating-point numbers
are not integer string/fret values. Each rest object requires exactly
`"rest": true` and `duration`, without a string or fret.

Durations must be strings: `"1"`, `"2"`, `"4"`, `"8"`, `"16"`, `"32"`, or
`"64"`, optionally followed by one dot, such as `"4."`. Every measure must
contain exactly the declared meter. A passage must include a pitched note;
rest-only measures are allowed within such a passage.

Missing fields, unknown fields, invalid values, duplicate JSON keys, comments,
NaN/Infinity, and malformed JSON are rejected. Unknown technique or chord
fields are not silently ignored. Errors identify the measure and event where
possible, numbered from 1.

String/fret data determines sounding pitch but carries no enharmonic spelling
or key information. Staff output therefore uses natural/sharp pitch spellings,
with accidentals as needed. For example, the same fret may be written D-sharp
where a musician might prefer E-flat. No key is inferred. Pitches, durations,
rests, and measure boundaries are preserved, without an extra octave shift.

For `tab` or `both` output, explicit input string/fret choices are preserved,
including equivalent pitches on different strings. This differs from the
automatic lowest-fret policy for LilyPond input. If music passes through that
automatic policy during a round trip, string choice can change; sounding
pitches and durations must not. Original enharmonic spelling cannot be
recovered from fret data alone.

This is a custom, documented position format. It is not general ASCII tab,
Guitar Pro, Power Tab, or LilyPond note pitches with string hints.

## LilyPond input format

The input must contain exactly this kind of passage, not a full LilyPond score:

```lilypond
\language "english"
\absolute {
  \time 4/4
  e,4 a,4 d4 g4 |
  b4 e'4 r2 |
}
```

This example plays the six open strings from low E to high E, followed by a
half-note rest. The fixtures contain original short passages, not songs.

Supported syntax:

- An optional `\version "x.y.z"` declaration, then `\language "english"`, then
  a single `\absolute { ... }` block beginning with `\time`.
- Meters `2/4`, `3/4`, `4/4`, and `6/8`.
- Lowercase English pitch names `a` through `g`. Accidentals are `s` for sharp,
  `f` for flat, `ss` for double sharp, or `ff` for double flat. For example,
  F-sharp is `fs`, B-flat is `bf`, and F-flat is `ff`.
- Absolute octave marks: apostrophes raise an octave and commas lower one.
  Mixed apostrophe/comma suffixes are not accepted.
- An explicit duration on **every** note or `r` rest: `1`, `2`, `4`, `8`, `16`,
  `32`, or `64`, optionally followed by one dot. Duration inheritance is not
  supported. For example, `e,4.` is a dotted quarter note.
- Whitespace between every note/rest and `|` barline. Each measure must be
  complete and end with `|`, including the final measure. No pickups or empty
  measures. A passage must contain at least one pitched note.
- Single-line `%` comments and blank lines.

All accidentals are part of the pitch name. There is no `\key` command in this
subset; staff output uses written accidentals as needed. Only the accepted
tokens are emitted. Input is not evaluated as LilyPond or Scheme code.

For example, a supported passage in 6/8 is:

```lilypond
\language "english"
\absolute {
  \time 6/8
  e,4. a,8 r8 b,8 |
}
```

## Pitch and tuning conventions

Input pitches are **sounding pitches**, not already octave-transposed guitar
staff pitches. In LilyPond absolute notation, `c` is C3, `c'` is middle C4,
`e,` is low E2, and `e'` is high E4. MIDI numbers below make the octave
convention explicit, with middle C4 equal to 60.

| String | Open sounding pitch | MIDI number |
| --- | --- | --- |
| 1, highest | E4 | 64 |
| 2 | B3 | 59 |
| 3 | G3 | 55 |
| 4 | D3 | 50 |
| 5 | A2 | 45 |
| 6, lowest | E2 | 40 |

The staff uses `\clef "treble_8"`, placing notes an octave above their sounding
pitch on the page without changing the music's pitches. Do not add another
octave transposition. Tab and staff retain the same sounding pitches and
durations.

The supported fret range is **0-20 inclusive**. The overall sounding range is
E2 through C6, MIDI 40-84. The same range restriction applies to staff-only
output, since this command validates a playable guitar passage.

For each LilyPond input note, choose the lowest available fret, then the lowest
string number if tied. This favors open strings and gives deterministic
assignments, but does not optimize hand movement or musical phrasing. Position
input instead keeps its explicit string/fret choices. The output specifies each
note's string explicitly, and LilyPond's native tablature engraver calculates
the displayed fret using standard `guitar-tuning`.

## Restrictions

Unsupported input fails with a message and a nonzero exit status. Measure
and token errors include line numbers where possible.

The LilyPond input parser does not accept complete scores, relative notation,
variables, includes, Scheme, nested music, chords/polyphony, existing string
assignments, key changes, alternate tunings, tuplets, ties, slurs, grace notes,
repeats, articulations, expressive techniques, block comments, or imported
ASCII/Guitar Pro/Power Tab/PDF/image notation. Generated scores are complete
documents and cannot be fed directly back into this narrow input parser.

## Tests

```sh
python -m unittest discover -s tests -v
```

Source and CLI tests cover pitch/octave spelling, all supported durations,
open strings, fretted passages crossing strings, dots/rests, range boundaries,
every playable semitone, output selection, rejected syntax, and file safety.
The expected-output fixture checks a complete generated score.

Position-input tests cover all 126 string/fret combinations, equivalent
pitches on different strings, strict JSON validation, all supported durations
and meters, CLI output selection, and error handling. Round trips through both
input representations check sounding pitches, durations, rests, and measures,
while allowing automatic string choice and enharmonic spelling to change.

When LilyPond is on `PATH`, the integration tests compile five LilyPond-input
passages and four position-input passages in all three output formats, making
27 scores. They check actual sounding pitches and durations in the parsed music
and capture the tab engraver's string/fret output, including open strings,
fretted notes, equivalent pitches on different strings, dots/rests, enharmonic
pitches, and fret 20. Without LilyPond, these tests skip; the other tests do not
verify engraving. On Omarchy, install LilyPond with `omarchy pkg add lilypond`.
