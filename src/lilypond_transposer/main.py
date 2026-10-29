"""Update the transposition of a lead sheet written in English LilyPond syntax."""

import argparse
from pathlib import Path
import re


PITCH = re.compile(r"[a-g](?:ff|ss|f|s)?(?:'+|,+)?\Z")
TRANSPOSE = re.compile(
    r"^(?P<prefix>\s*\\transpose\s+)(?P<source>\S+)"
    r"(?P<separator>\s+)(?P<target>\S+)(?P<suffix>\s+\{.*)$"
)


def normalize_key(value):
    """Accept common accidentals and return an English LilyPond pitch name."""
    value = value.lower().strip()
    match = re.fullmatch(r"([a-g])(bb|##|ff|ss|b|#|f|s|flat|sharp)?", value)
    if not match:
        raise ValueError(f"invalid target key {value!r}; use a pitch such as C, Bb, or F#")
    note, accidental = match.groups()
    accidental = (accidental or "").replace("flat", "f").replace("sharp", "s")
    return note + accidental.replace("b", "f").replace("#", "s")


def transpose_contents(contents, key, octave=None, lyrics="off"):
    """Replace destinations, leaving LilyPond to transpose notes and key events."""
    key = normalize_key(key)
    destination = key + {None: "", "up": "'", "down": ","}[octave]
    new_contents = []
    in_lyrics_block = False
    found_transpose = False

    for number, line in enumerate(contents.splitlines(keepends=True), start=1):
        stripped = line.strip()
        if re.match(r"\\transpose\b", stripped):
            match = TRANSPOSE.fullmatch(line.rstrip("\r\n"))
            if not match or not all(
                PITCH.fullmatch(match.group(name)) for name in ("source", "target")
            ):
                raise ValueError(
                    f"line {number}: malformed \\transpose; expected "
                    "\\transpose <source> <target> { with English LilyPond pitches"
                )
            start, end = match.span("target")
            line = line[:start] + destination + line[end:]
            found_transpose = True

        # Preserve the existing simple, single-block lyrics toggle.
        if "\\addlyrics" in stripped:
            in_lyrics_block = True
        if in_lyrics_block:
            if lyrics == "off" and not stripped.startswith("%"):
                line = "% " + line
            elif lyrics == "on" and stripped.startswith("%"):
                line = line.lstrip("% ")
        if in_lyrics_block and "}" in stripped:
            in_lyrics_block = False
        new_contents.append(line)

    if not found_transpose:
        raise ValueError(
            "no supported \\transpose statement found; wrap the score music in "
            "\\transpose <source> <target> { ... }"
        )
    return "".join(new_contents)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Transpose a LilyPond file from one key to another.")
    parser.add_argument("song_file", help="The LilyPond .ly file you would like to transpose")
    parser.add_argument("key", help="Destination reference pitch, e.g. D, Bb, F#")
    parser.add_argument(
        "--octave", choices=["up", "down"], default=None,
        help="Shift the transposed music up or down one octave",
    )
    parser.add_argument("--lyrics", choices=["on", "off"], default="off", help="Include lyrics")
    args = parser.parse_args(argv)
    try:
        args.key = normalize_key(args.key)
    except ValueError as error:
        parser.error(str(error))
    song = Path(args.song_file)
    output_file = song.with_name(f"{song.stem}-{args.key}.ly")
    try:
        contents = song.read_text(encoding="utf-8")
        result = transpose_contents(contents, args.key, args.octave, args.lyrics)
        output_file.write_text(result, encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(f"Created: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
