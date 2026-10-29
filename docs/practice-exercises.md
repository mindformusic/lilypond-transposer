# Chord-progression practice charts

Generate an editable LilyPond chart in a selected major key. Each chart has four
measures in 4/4, with chord symbols above a rhythmic staff containing measure
rests. Use the symbols to practice your own voicings or improvisation. The
generator does not provide playable notes, a melody, or accompaniment.

## Usage

Requires Python 3. Run from the repository root:

```sh
python src/lilypond_transposer/generate.py jazz-251 Bb --output practice.ly
```

This writes `practice.ly` without running LilyPond. To render it, install
LilyPond 2.24.3 or newer and run:

```sh
lilypond practice.ly
```

The chart uses standard LilyPond fonts. No jazz-font installation is required.
On Omarchy, LilyPond can be installed with `omarchy pkg add lilypond`.

Existing output files are protected. Pass `--force` to replace one:

```sh
python src/lilypond_transposer/generate.py pop F# --output practice.ly --force
```

The destination directory must already exist. Use `--help` for CLI options.

## Progressions

Each chord lasts one whole measure. Roman numerals describe scale degrees in
the selected major key. Uppercase numerals indicate major triads, lowercase
numerals indicate minor triads, and the suffixes specify seventh chords.

| Name | Functions | Chords in C major |
| --- | --- | --- |
| `pop` | I–V–vi–IV | C, G, Am, F |
| `jazz-251` | ii7–V7–Imaj7–Imaj7 | Dm7, G7, Cmaj7, Cmaj7 |

The jazz template uses a minor seventh chord on ii, a dominant seventh on V,
and a major seventh on I. The tonic repeats for a fourth measure, making both
templates four bars long. The repeated chord symbol remains visible.

## Supported tonics

The 15 supported major-key spellings are C, G, D, A, E, B, F-sharp, C-sharp,
F, B-flat, E-flat, A-flat, D-flat, G-flat, and C-flat.

Input is case-insensitive and accepts `Bb`, `Bflat`, or LilyPond's English `bf`
for B-flat, and `F#`, `Fsharp`, or `fs` for F-sharp. Enter only the tonic, not
`Bb major`. Enharmonic spellings remain distinct, so F-sharp and G-flat
produce differently spelled chords.

Templates are written in C major and transposed by LilyPond. Unsupported
progressions, invalid pitches, theoretical keys outside this list, and output
errors produce a nonzero exit status with a message.

Minor keys, arbitrary progressions, custom durations, scale exercises, voicing
selection, and automatic rendering are outside this first version. The
existing transposition CLI is unchanged.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests cover template selection, tonic normalization, generated source, CLI
errors, and overwrite protection. `tests/fixtures/pop-c.ly` is the expected
source for the pop chart in C, not a copyrighted song.

When LilyPond is on `PATH`, integration tests compile both progressions in all
15 supported keys, checking actual chord spellings, chord durations, and the
four-bar rhythmic staff. Without LilyPond, those checks skip; source tests
alone do not verify musical interpretation or engraving.
