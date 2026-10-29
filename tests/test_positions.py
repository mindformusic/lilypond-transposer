"""Explicit string/fret input and sounding-music round trips."""

import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_tablature import FIXTURES, INSPECT_MUSIC, SCRIPT, passage, tablature


def document(measures, meter="4/4"):
    return {"version": 1, "tuning": "standard", "meter": meter, "measures": measures}


def note(string=1, fret=0, duration="1"):
    return {"string": string, "fret": fret, "duration": duration}


def sounding_events(melody):
    return [[(None if event.pitch == "r" else tablature.pitch_to_midi(event.pitch), event.duration)
             for event in measure] for measure in melody.measures]


def as_lilypond_input(melody):
    body = " ".join(" ".join(event.pitch + event.duration for event in measure) + " |"
                    for measure in melody.measures)
    return passage(body, melody.meter)


def as_position_input(melody):
    measures = [[{"rest": True, "duration": event.duration} if event.pitch == "r"
                 else note(event.string, event.fret, event.duration)
                 for event in measure] for measure in melody.measures]
    return json.dumps(document(measures, melody.meter))


class PositionTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True)

    def test_open_and_fretted_strings(self):
        for fixture, pitches, fret in (
            ("guitar-positions-open.json", [40, 45, 50, 55, 59, 64], 0),
            ("guitar-positions-fretted.json", [41, 46, 51, 56, 60, 65], 1),
        ):
            with self.subTest(fixture=fixture):
                melody = tablature.parse_positions((FIXTURES / fixture).read_text())
                events = [event for measure in melody.measures for event in measure]
                self.assertEqual([tablature.pitch_to_midi(event.pitch) for event in events[:-1]], pitches)
                self.assertEqual([(event.string, event.fret) for event in events[:-1]],
                                 [(string, fret) for string in (6, 5, 4, 3, 2, 1)])
                self.assertEqual((events[-1].pitch, events[-1].duration), ("r", "2"))
                if fret == 1:
                    self.assertEqual([event.pitch for event in events[:-1]],
                                     ["f,", "as,", "ds", "gs", "c'", "f'"])

    def test_equivalent_positions_preserve_pitch_and_explicit_strings(self):
        source = (FIXTURES / "guitar-positions-equivalent.json").read_text()
        melody = tablature.parse_positions(source)
        self.assertEqual(sounding_events(melody), [[(64, "4")] * 4])
        self.assertEqual([(event.string, event.fret) for event in melody.measures[0]],
                         [(1, 0), (2, 5), (3, 9), (4, 14)])
        generated = tablature.convert_contents(source, "tab", "positions")
        for token in ("e'4\\1", "e'4\\2", "e'4\\3", "e'4\\4"):
            self.assertIn(token, generated)

    def test_every_string_fret_and_pitch_duration_round_trip(self):
        for string, opened in enumerate((64, 59, 55, 50, 45, 40), start=1):
            for fret in range(21):
                with self.subTest(string=string, fret=fret):
                    original = tablature.parse_positions(json.dumps(document([[note(string, fret)]])))
                    self.assertEqual(sounding_events(original), [[(opened + fret, "1")]])
                    forward = tablature.parse_melody(as_lilypond_input(original))
                    reverse = tablature.parse_positions(as_position_input(forward))
                    self.assertEqual(sounding_events(forward), sounding_events(original))
                    self.assertEqual(sounding_events(reverse), sounding_events(original))
        original = tablature.parse_positions((FIXTURES / "guitar-positions-equivalent.json").read_text())
        forward = tablature.parse_melody(as_lilypond_input(original))
        self.assertEqual([event.string for event in forward.measures[0]], [1, 1, 1, 1])

    def test_forward_fixture_round_trips_include_dots_rests_and_bars(self):
        for fixture in ("guitar-open-strings.ly", "guitar-fretted.ly", "guitar-dotted.ly"):
            with self.subTest(fixture=fixture):
                original = tablature.parse_melody((FIXTURES / fixture).read_text())
                reverse = tablature.parse_positions(as_position_input(original))
                forward = tablature.parse_melody(as_lilypond_input(reverse))
                self.assertEqual(sounding_events(reverse), sounding_events(original))
                self.assertEqual(sounding_events(forward), sounding_events(original))
                self.assertEqual(forward.meter, original.meter)

    def test_all_durations_and_meters(self):
        for denominator in (1, 2, 4, 8, 16, 32, 64):
            with self.subTest(denominator=denominator):
                source = json.dumps(document([[note(duration=str(denominator))] * denominator]))
                melody = tablature.parse_positions(source)
                self.assertEqual(len(melody.measures[0]), denominator)
        for meter, measures in (
            ("2/4", [[note(duration="2")]]),
            ("3/4", [[note(duration="2.")]]),
            ("4/4", [[note(duration="1")]]),
            ("6/8", [[note(6, 0, "4."), {"rest": True, "duration": "4."}]]),
        ):
            with self.subTest(meter=meter):
                melody = tablature.parse_positions(json.dumps(document(measures, meter)))
                self.assertEqual(melody.meter, meter)
                self.assertEqual(sounding_events(tablature.parse_melody(as_lilypond_input(melody))),
                                 sounding_events(melody))

    def test_missing_extra_and_unsupported_document_fields(self):
        valid = document([[note()]])
        bad_documents = [None, [], "tab", {}]
        for field in valid:
            modified = copy.deepcopy(valid)
            del modified[field]
            bad_documents.append(modified)
        for field, value in (("version", True), ("version", 1.0), ("version", "1"), ("version", 2),
                             ("tuning", "drop-d"), ("tuning", [64, 59, 55, 50, 45, 38]),
                             ("meter", "5/4"), ("meter", []), ("measures", []),
                             ("measures", {}), ("measures", [None]), ("measures", [[]])):
            modified = copy.deepcopy(valid)
            modified[field] = value
            bad_documents.append(modified)
        modified = copy.deepcopy(valid)
        modified["technique"] = "slide"
        bad_documents.append(modified)
        for data in bad_documents:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    tablature.parse_positions(json.dumps(data))

    def test_invalid_positions_durations_and_event_shapes(self):
        bad_events = [None, [], [note(), note()], "1:0", {}, {"duration": "1"},
                      {"rest": False, "duration": "1"}, {"rest": 1, "duration": "1"},
                      {"rest": True, "duration": "1", "string": 1}]
        for field, values in (
            ("string", (0, 7, -1, 1.0, True, "1", None)),
            ("fret", (-1, 21, 0.0, False, "0", None)),
            ("duration", (None, 4, "", "0", "3", "128", "4..", "4~", "quarter", " 4")),
        ):
            for value in values:
                event = note()
                event[field] = value
                bad_events.append(event)
        for field in ("string", "fret", "duration"):
            event = note()
            del event[field]
            bad_events.append(event)
        for field in ("bend", "slide", "notes", "chord", "tuning"):
            event = note()
            event[field] = True
            bad_events.append(event)
        for event in bad_events:
            with self.subTest(event=event):
                with self.assertRaisesRegex(ValueError, "measure 1, event 1"):
                    tablature.parse_positions(json.dumps(document([[event]])))

    def test_bad_measures_and_rest_only_passages(self):
        for events in ([note(duration="4")], [note(), note(duration="4")]):
            with self.assertRaisesRegex(ValueError, "measure 1 must contain exactly 4/4"):
                tablature.parse_positions(json.dumps(document([events])))
        with self.assertRaisesRegex(ValueError, "pitched note"):
            tablature.parse_positions(json.dumps(document([[{"rest": True, "duration": "1"}]])))
        melody = tablature.parse_positions(json.dumps(document([
            [note()], [{"rest": True, "duration": "1"}],
        ])))
        self.assertEqual(sounding_events(melody), [[(64, "1")], [(None, "1")]])

    def test_strict_json_errors(self):
        for source, message in (
            ('{"version":', "line 1, column"),
            ('{"version":1,"version":1}', "duplicate JSON field"),
            ('{"measures":[[{"string":1,"string":2}]]}', "duplicate JSON field"),
            ('{"version":NaN}', "invalid JSON number"),
            ('{"version":Infinity}', "invalid JSON number"),
            (json.dumps(document([[note()]])) + " trailing", "invalid position JSON"),
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, message):
                    tablature.parse_positions(source)
        source = json.dumps(document([[note()]]))
        with self.assertRaisesRegex(ValueError, "input format"):
            tablature.convert_contents(source, input_format="ascii")

    def test_open_string_expected_output_matches_existing_fixture(self):
        source = (FIXTURES / "guitar-positions-open.json").read_text()
        expected = (FIXTURES / "guitar-open-strings-both.expected.ly").read_text()
        self.assertEqual(tablature.convert_contents(source, input_format="positions"), expected)

    def test_cli_explicit_input_format_and_all_output_modes(self):
        song = FIXTURES / "guitar-positions-open.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "staff.ly"
            result = self.run_cli(song, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            for representation in ("staff", "tab", "both"):
                result = self.run_cli(song, "--input-format", "positions", "--format", representation,
                                      "--output", output, "--force")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_text(), tablature.convert_contents(
                    song.read_text(), representation, "positions"))

    def test_cli_position_errors_do_not_write_or_truncate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            song, output = Path(directory) / "positions.json", Path(directory) / "staff.ly"
            song.write_text(json.dumps(document([[note(fret=-1)]])))
            for existing in (False, True):
                if existing:
                    output.write_text("existing score\n")
                result = self.run_cli(song, "--input-format", "positions", "--output", output, "--force")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fret must be", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                if existing:
                    self.assertEqual(output.read_text(), "existing score\n")
                else:
                    self.assertFalse(output.exists())


@unittest.skipUnless(shutil.which("lilypond"), "LilyPond not installed; source tests only")
class LilyPondPositionTests(unittest.TestCase):
    def test_reverse_conversion_pitches_durations_and_explicit_positions(self):
        cases = (
            ((FIXTURES / "guitar-positions-open.json").read_text(),
             [(40, "1/4"), (45, "1/4"), (50, "1/4"), (55, "1/4"), (59, "1/4"), (64, "1/4"), ("rest", "1/2")],
             [(6, 0), (5, 0), (4, 0), (3, 0), (2, 0), (1, 0)]),
            ((FIXTURES / "guitar-positions-fretted.json").read_text(),
             [(41, "1/4"), (46, "1/4"), (51, "1/4"), (56, "1/4"), (60, "1/4"), (65, "1/4"), ("rest", "1/2")],
             [(6, 1), (5, 1), (4, 1), (3, 1), (2, 1), (1, 1)]),
            ((FIXTURES / "guitar-positions-equivalent.json").read_text(),
             [(64, "1/4")] * 4, [(1, 0), (2, 5), (3, 9), (4, 14)]),
            (json.dumps(document([[note(6, 0, "4."), {"rest": True, "duration": "8"},
                                   note(5, 2, "8"), note(1, 20, "8")]], "6/8")),
             [(40, "3/8"), ("rest", "1/8"), (47, "1/8"), (84, "1/8")], [(6, 0), (5, 2), (1, 20)]),
        )
        for index, (source, expected_events, expected_positions) in enumerate(cases):
            for representation in ("staff", "tab", "both"):
                with self.subTest(case=index, representation=representation):
                    generated = tablature.convert_contents(source, representation, "positions")
                    generated = generated.replace("\\score {", INSPECT_MUSIC + "\n\\score {")
                    generated = generated.replace(
                        "stringTunings = #guitar-tuning",
                        "stringTunings = #guitar-tuning tablatureFormat = #test-tab-format",
                    )
                    labels = ("staff", "tab") if representation == "both" else (representation,)
                    for label in labels:
                        generated += f'\n#(inspect-music "{label}" {label}_music)\n'
                    with tempfile.TemporaryDirectory() as directory:
                        song = Path(directory) / "test.ly"
                        song.write_text(generated)
                        result = subprocess.run(
                            ["lilypond", "-o", str(Path(directory) / "score"), str(song)],
                            capture_output=True, text=True, timeout=60,
                        )
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertNotIn("warning:", result.stderr.lower())
                        self.assertTrue((Path(directory) / "score.pdf").is_file())
                        for label in labels:
                            actual = re.findall(rf"TEST-EVENT {label} (\S+) (\S+)", result.stdout)
                            self.assertEqual(actual, [(str(pitch), duration) for pitch, duration in expected_events])
                        actual_positions = [tuple(map(int, pair))
                                            for pair in re.findall(r"TEST-TAB (\d+) (\d+)", result.stdout)]
                        self.assertEqual(actual_positions, [] if representation == "staff" else expected_positions)


if __name__ == "__main__":
    unittest.main()
