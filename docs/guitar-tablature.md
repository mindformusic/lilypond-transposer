# Guitar staff and tablature output

Convert a small, explicit subset of LilyPond melody notation to guitar staff
notation, tablature, or both. This is notation-to-tab support for issue #8,
part of #4. Reverse conversion from string/fret data is tracked separately in
#9 and is not implemented here.

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

## Input format

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

For each note, choose the lowest available fret, then the lowest string number
if tied. This favors open strings and gives deterministic assignments, but does
not optimize hand movement or musical phrasing. The output specifies each
note's string explicitly, and LilyPond's native tablature engraver calculates
the displayed fret using standard `guitar-tuning`.

## Restrictions

Unsupported input fails with a message and a nonzero exit status. Measure
and token errors include line numbers where possible.

This first version does not accept complete scores, relative notation,
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

When LilyPond is on `PATH`, the integration test compiles five passages in all
three output formats. It checks actual sounding pitches and durations in the
parsed music and captures the tab engraver's string/fret output, including
open strings, fretted notes, dots/rests, enharmonic pitches, and fret 20.
Without LilyPond, this test skips; the other tests do not verify engraving.
On Omarchy, install LilyPond with `omarchy pkg add lilypond`.
