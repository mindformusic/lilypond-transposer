"""Convert explicit melodies or guitar string/fret data to staff and tablature."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re


# MIDI sounding pitches, string 1 (highest) through string 6 (lowest).
TUNING = (64, 59, 55, 50, 45, 40)
MAX_FRET = 20
METERS = {"2/4", "3/4", "4/4", "6/8"}
PITCH = r"[a-g](?:ff|ss|f|s)?(?:'+|,+)?"
NOTE = re.compile(rf"(?P<pitch>{PITCH}|r)(?P<duration>64|32|16|8|4|2|1)(?P<dot>\.?)\Z")
DURATION = re.compile(r"(?:64|32|16|8|4|2|1)\.?\Z")
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


def midi_to_pitch(midi):
    """Use natural/sharp spellings when fret data has no enharmonic information."""
    name = ("c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b")[midi % 12]
    octave = midi // 12 - 4
    return name + "'" * max(0, octave) + "," * max(0, -octave)


def meter_length(meter):
    if not isinstance(meter, str) or meter not in METERS:
        raise ValueError(f"unsupported meter {meter!r}; choose 2/4, 3/4, 4/4, or 6/8")
    numerator, denominator = map(int, meter.split("/"))
    return Fraction(numerator, denominator)


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError(f"invalid JSON number {value!r}; NaN and Infinity are unsupported")


def _require_fields(value, fields, location):
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object")
    missing = fields - value.keys()
    extra = value.keys() - fields
    if missing:
        raise ValueError(f"{location}: missing field(s): {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{location}: unsupported field(s): {', '.join(sorted(extra))}")


def parse_positions(source):
    """Read the version-1, standard-tuning string/fret JSON format."""
    try:
        data = json.loads(source, object_pairs_hook=_unique_json_object,
                          parse_constant=_reject_json_constant)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid position JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    _require_fields(data, {"version", "tuning", "meter", "measures"}, "position JSON")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("position JSON version must be the integer 1")
    if data["tuning"] != "standard":
        raise ValueError('position JSON tuning must be "standard": strings 1-6 are E4 B3 G3 D3 A2 E2')
    expected_length = meter_length(data["meter"])
    if not isinstance(data["measures"], list) or not data["measures"]:
        raise ValueError("measures must be a nonempty array of measures")
    measures = []
    has_note = False
    for measure_index, raw_measure in enumerate(data["measures"], start=1):
        if not isinstance(raw_measure, list) or not raw_measure:
            raise ValueError(f"measure {measure_index}: expected a nonempty array of events")
        events = []
        for event_index, raw_event in enumerate(raw_measure, start=1):
            location = f"measure {measure_index}, event {event_index}"
            is_rest = isinstance(raw_event, dict) and "rest" in raw_event
            fields = {"rest", "duration"} if is_rest else {"string", "fret", "duration"}
            _require_fields(raw_event, fields, location)
            duration = raw_event["duration"]
            if not isinstance(duration, str) or not DURATION.fullmatch(duration):
                raise ValueError(
                    f"{location}: duration must be a string: 1, 2, 4, 8, 16, 32, or 64, optionally dotted"
                )
            if is_rest:
                if raw_event["rest"] is not True:
                    raise ValueError(f"{location}: rest must be true")
                events.append(Event("r", duration))
                continue
            string, fret = raw_event["string"], raw_event["fret"]
            if type(string) is not int or not 1 <= string <= len(TUNING):
                raise ValueError(f"{location}: string must be an integer from 1 to 6, with 1 the highest E")
            if type(fret) is not int or not 0 <= fret <= MAX_FRET:
                raise ValueError(f"{location}: fret must be an integer from 0 to {MAX_FRET}")
            events.append(Event(midi_to_pitch(TUNING[string - 1] + fret), duration, string, fret))
            has_note = True
        if sum((duration_length(event.duration) for event in events), Fraction(0)) != expected_length:
            raise ValueError(f"measure {measure_index} must contain exactly {data['meter']}")
        measures.append(tuple(events))
    if not has_note:
        raise ValueError("the passage must contain at least one pitched note")
    return Melody(data["meter"], tuple(measures))


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
    measure_length = meter_length(meter)
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


def convert_contents(source, representation="both", input_format="lilypond"):
    if input_format == "lilypond":
        melody = parse_melody(source)
    elif input_format == "positions":
        melody = parse_positions(source)
    else:
        raise ValueError("input format must be lilypond or positions")
    return render_score(melody, representation)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert absolute LilyPond melodies or string/fret JSON to guitar staff/tab notation.",
        epilog="Standard tuning E2 A2 D3 G3 B3 E4; frets 0-20. LilyPond input uses "
               "lowest-fret assignment; positions input preserves explicit strings and frets.",
    )
    parser.add_argument("input", type=Path, help="Input melody .ly or explicit string/fret .json file")
    parser.add_argument("--input-format", choices=["lilypond", "positions"], default="lilypond",
                        help="Input syntax, not inferred from the filename (default: lilypond)")
    parser.add_argument("--output", type=Path, required=True, help="Destination LilyPond file")
    parser.add_argument("--format", choices=["staff", "tab", "both"], default="both")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("input and output must be different files, even with --force")
        if args.output.exists() and args.input.exists() and args.output.samefile(args.input):
            raise ValueError("input and output must be different files, even with --force")
        contents = convert_contents(args.input.read_text(encoding="utf-8"), args.format, args.input_format)
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
