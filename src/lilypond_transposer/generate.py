"""Generate four-bar LilyPond chord charts for major-key practice."""

import argparse
from pathlib import Path
import re


# Templates are in C major. LilyPond handles spelling in the requested key.
PROGRESSIONS = {
    "pop": {
        "title": "Pop progression",
        "functions": "I | V | vi | IV",
        "chords": "c1 | g1 | a1:m | f1 |",
    },
    "jazz-251": {
        "title": "Jazz ii-V-I",
        "functions": "ii7 | V7 | Imaj7 | Imaj7",
        "chords": "d1:m7 | g1:7 | c1:maj7 | c1:maj7 |",
    },
}
MAJOR_KEYS = {
    "cf", "gf", "df", "af", "ef", "bf", "f", "c",
    "g", "d", "a", "e", "b", "fs", "cs",
}


def normalize_tonic(value):
    """Accept common accidentals and the 15 conventional major-key spellings."""
    match = re.fullmatch(r"([a-g])(b|#|f|s|flat|sharp)?", value.lower().strip())
    if not match:
        raise ValueError(f"invalid tonic {value!r}; use a major-key tonic such as C, Bb, or F#")
    note, accidental = match.groups()
    accidental = (accidental or "").replace("flat", "f").replace("sharp", "s")
    tonic = note + accidental.replace("b", "f").replace("#", "s")
    if tonic not in MAJOR_KEYS:
        raise ValueError(
            f"unsupported major-key tonic {value!r}; use C, G, D, A, E, B, F#, C#, "
            "F, Bb, Eb, Ab, Db, Gb, or Cb"
        )
    return tonic


def generate_score(progression, tonic):
    """Return editable source, without rendering or choosing chord voicings."""
    if progression not in PROGRESSIONS:
        raise ValueError(
            f"unsupported progression {progression!r}; choose " + ", ".join(PROGRESSIONS)
        )
    tonic = normalize_tonic(tonic)
    template = PROGRESSIONS[progression]
    key_label = tonic[0].upper() + tonic[1:].replace("f", "b").replace("s", "#")
    return rf'''\version "2.24.3"
\language "english"

\header {{
  title = "{template['title']} in {key_label} major"
  subtitle = "{template['functions']}"
  tagline = ##f
}}

chord_sequence = \chordmode {{
  {template['chords']}
}}

music = {{
  \transpose c {tonic} {{
    <<
      \new ChordNames {{ \chord_sequence }}
      \new RhythmicStaff {{
        \time 4/4
        R1*4
        \bar "|."
      }}
    >>
  }}
}}

\score {{
  \music
  \layout {{ indent = 0 }}
}}
'''


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a four-bar major-key chord chart, without melody or voicings."
    )
    parser.add_argument("progression", choices=PROGRESSIONS, help="Named progression template")
    parser.add_argument("tonic", help="Major-key tonic, e.g. C, Bb, or F#")
    parser.add_argument("--output", required=True, type=Path, help="Destination LilyPond .ly file")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    args = parser.parse_args(argv)
    try:
        contents = generate_score(args.progression, args.tonic)
        with args.output.open("w" if args.force else "x", encoding="utf-8") as output:
            output.write(contents)
    except FileExistsError:
        parser.error(f"output {args.output} already exists; use --force to overwrite")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
