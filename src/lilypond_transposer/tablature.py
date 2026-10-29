"""Convert a strict subset of absolute LilyPond melodies to guitar tablature."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re


# MIDI sounding pitches, string 1 (highest) through string 6 (lowest).
TUNING = (64, 59, 55, 50, 45, 40)
MAX_FRET = 20
METERS = {"2/4", "3/4", "4/4", "6/8"}
PITCH = r"[a-g](?:ff|ss|f|s)?(?:'+|,+)?"
NOTE = re.compile(rf"(?P<pitch>{PITCH}|r)(?P<duration>64|32|16|8|4|2|1)(?P<dot>\.?)\Z")
HEADER = re.compile(
    r'\s*(?:\\version\s+"\d+\.\d+\.\d+"\s*)?'
    r'\\language\s+"english"\s+\\absolute\s*\{\s*'
    r'\\time\s+(?P<meter>\d+/\d+)\s+(?P<body>.*?)\s*\}\s*\Z',
    re.DOTALL,
)


@dataclass(frozen=True)
class Event:
    pitch: str
    duration: str
    string: int = 0
    fret: int = 0


@dataclass(frozen=True)
class Melody:
    meter: str
    measures: tuple


def pitch_to_midi(pitch):
    """LilyPond absolute c is C3, c' is C4, and e, is the guitar's low E2."""
    if not re.fullmatch(PITCH, pitch):
        raise ValueError(f"invalid English absolute pitch {pitch!r}")
    semitone = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[pitch[0]]
    return (48 + semitone + pitch.count("s") - pitch.count("f", 1)
            + 12 * (pitch.count("'") - pitch.count(",")))


def choose_position(midi):
    """Prefer the lowest fret, then the lowest string number in a tie."""
    candidates = [(midi - open_pitch, string)
                  for string, open_pitch in enumerate(TUNING, start=1)
                  if 0 <= midi - open_pitch <= MAX_FRET]
    if not candidates:
        raise ValueError("pitch is outside standard guitar tuning with frets 0-20, E2 through C6")
    fret, string = min(candidates)
    return string, fret


def duration_length(duration):
    return Fraction(1, int(duration.rstrip("."))) * (Fraction(3, 2) if duration.endswith(".") else 1)


def parse_melody(source):
    """Parse only the documented header, explicit note/rest durations, and bars."""
    if "%{" in source or "%}" in source:
        raise ValueError("block comments are unsupported; use single-line % comments")
    # Mask comments so token locations still refer to the original file.
    source = re.sub(r"%[^\n]*", lambda match: " " * len(match[0]), source)
    header = HEADER.fullmatch(source)
    if not header:
        raise ValueError(
            'expected \\language "english" followed by \\absolute { \\time 4/4 ... }; '
            "complete scores, relative notation, and other commands are unsupported"
        )
    meter = header["meter"]
    if meter not in METERS:
        raise ValueError(f"unsupported meter {meter!r}; choose 2/4, 3/4, 4/4, or 6/8")
    numerator, denominator = map(int, meter.split("/"))
    measure_length = Fraction(numerator, denominator)
    measures, events = [], []
    elapsed = Fraction(0)
    has_note = False
    for token in re.finditer(r"\S+", header["body"]):
        offset = header.start("body") + token.start()
        line = source.count("\n", 0, offset) + 1
        value = token[0]
        if value == "|":
            if elapsed != measure_length:
                raise ValueError(f"line {line}: measure {len(measures) + 1} must contain exactly {meter}")
            measures.append(tuple(events))
            events, elapsed = [], Fraction(0)
            continue
        match = NOTE.fullmatch(value)
        if not match:
            raise ValueError(
                f"line {line}: unsupported token {value!r}; use whitespace-separated single "
                "absolute notes or rests with explicit durations and | barlines"
            )
        pitch = match["pitch"]
        duration = match["duration"] + match["dot"]
        string, fret = 0, 0
        if pitch != "r":
            try:
                string, fret = choose_position(pitch_to_midi(pitch))
            except ValueError as error:
                raise ValueError(f"line {line}: {pitch!r}: {error}") from error
            has_note = True
        elapsed += duration_length(duration)
        if elapsed > measure_length:
            raise ValueError(f"line {line}: measure {len(measures) + 1} exceeds {meter}")
        events.append(Event(pitch, duration, string, fret))
    if events:
        raise ValueError("each complete measure must end with a whitespace-separated | barline")
    if not has_note:
        raise ValueError("the passage must contain at least one pitched note")
    return Melody(meter, tuple(measures))


def render_score(melody, representation="both"):
    if representation not in {"staff", "tab", "both"}:
        raise ValueError("output format must be staff, tab, or both")
    definitions, staves = [], []
    for kind in ("staff", "tab"):
        if representation not in {kind, "both"}:
            continue
        measures = []
        for measure in melody.measures:
            tokens = [event.pitch + event.duration
                      + (f"\\{event.string}" if kind == "tab" and event.string else "")
                      for event in measure]
            measures.append("  " + " ".join(tokens) + " |")
        clef = '  \\clef "treble_8"\n' if kind == "staff" else "  \\tabFullNotation\n"
        definitions.append(
            f"{kind}_music = \\absolute {{\n{clef}  \\time {melody.meter}\n"
            + "\n".join(measures) + '\n  \\bar "|."\n}'
        )
        if kind == "staff":
            staves.append("    \\new Staff { \\staff_music }")
        else:
            staves.append("    \\new TabStaff \\with { stringTunings = #guitar-tuning } { \\tab_music }")
    return ('\\version "2.24.3"\n\\language "english"\n'
            '% Standard tuning: string 1 = E4, 2 = B3, 3 = G3, 4 = D3, 5 = A2, 6 = E2.\n'
            '% Sounding pitches; guitar staff uses an octave-down treble clef.\n\n'
            + "\n\n".join(definitions)
            + "\n\n\\score {\n  <<\n" + "\n".join(staves)
            + "\n  >>\n  \\layout {}\n}\n")


def convert_contents(source, representation="both"):
    return render_score(parse_melody(source), representation)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert explicit absolute LilyPond melodies to guitar staff/tab notation.",
        epilog="Standard tuning E2 A2 D3 G3 B3 E4; frets 0-20; lowest-fret assignment. "
               "Input must use the documented English, absolute, single-note subset.",
    )
    parser.add_argument("input", type=Path, help="Input melody .ly file, not an arbitrary score")
    parser.add_argument("--output", type=Path, required=True, help="Destination LilyPond file")
    parser.add_argument("--format", choices=["staff", "tab", "both"], default="both")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("input and output must be different files, even with --force")
        if args.output.exists() and args.input.exists() and args.output.samefile(args.input):
            raise ValueError("input and output must be different files, even with --force")
        contents = convert_contents(args.input.read_text(encoding="utf-8"), args.format)
        with args.output.open("w" if args.force else "x", encoding="utf-8") as output:
            output.write(contents)
    except FileExistsError:
        parser.error(f"output {args.output} already exists; use --force to overwrite")
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
