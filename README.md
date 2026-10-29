# lilypond-transposer
A simple CLI sheet music transposer that uses LilyPond.

# Background
This code was featured in a YouTube video talking about how valuable LilyPond could be to public music education:

# Usage

Requires Python 3. LilyPond is needed to render the output, but not to run the
transposer. This tool is mainly intended for jazz lead sheets with chords and
melody.

Use English LilyPond pitch names by including `\language "english"` in your
file. Wrap the score's music in a `\transpose` block:

```
\score
{
  \transpose c c {
  <<
    \new ChordNames
        {
           \chord_sequence
        }
    \new Staff
        {
          \melody
        }
  >>
  }
  \layout {}
}
```

The chord block should start with:
```
chord_sequence = \chords
```

And the melody:
```
melody = \relative
```

From the repository root, run:

```sh
python src/lilypond_transposer/main.py song.ly d --octave down --lyrics on
```

This writes `song-d.ly` beside the original without modifying it. Render the
generated file separately:

```sh
lilypond song-d.ly
```

The destination accepts pitch names such as `D`, `Bb`, `F#`, `Aflat`, or
English LilyPond spellings such as `bf` and `fs`. It is a pitch, not a mode or
a full key name such as `D major`. Lyrics default to `off`. The optional
`--octave up` or `--octave down` shifts all music inside the transpose block,
not just the melody.

## Source pitch and key signatures

LilyPond's `\transpose <source> <destination>` maps one reference pitch to
another. The CLI preserves the source and replaces the destination. For the
destination to mean the resulting tonic, the source reference must match the
original tonic, with the mode unchanged. For example:

| Original music | Input block | CLI destination | Generated block |
| --- | --- | --- | --- |
| C major | `\transpose c c {` | `d` | `\transpose c d {` |
| F major | `\transpose f f {` | `g` | `\transpose f g {` |
| C major | `\transpose c c {` | `Bb` | `\transpose c bf {` |

Keep the `\key` declaration inside the transposed music. It can be inside the
`melody` variable referenced by the block, as in the bundled examples.
LilyPond transposes that key signature together with the notes. The tool does
not rewrite `\key` separately, which would risk applying the transposition
twice. A `\key` declaration outside the block will not be transposed.

## Supported input

- Put `\transpose <source> <destination> {` on one line, with the command
  at the start of the line apart from indentation. Both reference pitches
  must be valid English LilyPond pitches, optionally with octave marks.
- Every supported transpose statement receives the requested destination.
  Multiple blocks must therefore use appropriate source references.
- Missing or malformed statements produce an error without writing output.
- This is a line-based editor, not a general LilyPond parser. Inline commands
  after other code, multiline transpose headers, and commands inside block
  comments are not supported. Single-line `%` comments are left alone, except
  when toggling lyrics.
- Lyrics toggling assumes a simple `\addlyrics` block without nested braces.

## Tests

Run the standard-library test suite from the repository root:

```sh
python -m unittest discover -s tests -v
```

The small fixtures in `tests/fixtures/` contain original test passages and do
not require the bundled jazz fonts. When `lilypond` is on `PATH`, the tests
compile generated scores to PDF and inspect LilyPond's transposed note pitches,
key tonic, and key-signature alterations. Cases cover C major to D major,
F major to G major, C major to B-flat major, and octave shifts.

Without LilyPond, the integration test is skipped. The remaining tests check
source transformations, pitch validation, CLI errors, lyrics, and file handling;
they do not verify engraving or musical interpretation. On Omarchy, install
LilyPond with `omarchy pkg add lilypond`.
