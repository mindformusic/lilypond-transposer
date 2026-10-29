"""Original guitar passages, source/CLI checks, and optional LilyPond checks."""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/lilypond_transposer/tablature.py"
FIXTURES = Path(__file__).parent / "fixtures"
SPEC = importlib.util.spec_from_file_location("tablature", SCRIPT)
tablature = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tablature
SPEC.loader.exec_module(tablature)


def passage(body, meter="4/4"):
    return '\\language "english"\n\\absolute {\n  \\time ' + meter + "\n  " + body + "\n}\n"


class TablatureTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
        )

    def test_absolute_pitch_conventions_and_accidentals(self):
        for pitch, midi in {
            "c": 48, "c'": 60, "e,": 40, "e'": 64, "c'''": 84,
            "bf,": 46, "fs": 54, "es": 53, "ff": 52, "css": 50, "dff": 48,
        }.items():
            with self.subTest(pitch=pitch):
                self.assertEqual(tablature.pitch_to_midi(pitch), midi)

    def test_open_strings(self):
        melody = tablature.parse_melody((FIXTURES / "guitar-open-strings.ly").read_text())
        notes = [event for measure in melody.measures for event in measure if event.pitch != "r"]
        self.assertEqual([(event.string, event.fret) for event in notes],
                         [(6, 0), (5, 0), (4, 0), (3, 0), (2, 0), (1, 0)])

    def test_fretted_notes_cross_strings(self):
        melody = tablature.parse_melody((FIXTURES / "guitar-fretted.ly").read_text())
        notes = [event for measure in melody.measures for event in measure if event.pitch != "r"]
        self.assertEqual([(event.string, event.fret) for event in notes],
                         [(6, 1), (5, 1), (4, 1), (3, 1), (2, 1), (1, 1)])
        for event, midi in zip(notes, (41, 46, 51, 56, 60, 65)):
            self.assertEqual((64, 59, 55, 50, 45, 40)[event.string - 1] + event.fret, midi)

    def test_lowest_fret_policy_across_entire_supported_range(self):
        for midi in range(40, 85):
            with self.subTest(midi=midi):
                string, fret = tablature.choose_position(midi)
                self.assertEqual((64, 59, 55, 50, 45, 40)[string - 1] + fret, midi)
                candidates = [(midi - opened, index)
                              for index, opened in enumerate((64, 59, 55, 50, 45, 40), 1)
                              if 0 <= midi - opened <= 20]
                self.assertEqual((fret, string), min(candidates))
                spelling = ("c", "cs", "d", "ef", "e", "f", "fs", "g", "af", "a", "bf", "b")[midi % 12]
                octave = midi // 12 - 4
                spelling += "'" * max(0, octave) + "," * max(0, -octave)
                note = tablature.parse_melody(passage(spelling + "1 |")).measures[0][0]
                self.assertEqual((note.string, note.fret), (string, fret))
                self.assertEqual(tablature.pitch_to_midi(note.pitch), midi)

    def test_range_boundaries(self):
        melody = tablature.parse_melody(passage("e,4 c'''4 |", "2/4"))
        self.assertEqual([(event.string, event.fret) for event in melody.measures[0]], [(6, 0), (1, 20)])
        for pitch in ("ef,", "cs'''", "c,,,,", "c''''"):
            with self.subTest(pitch=pitch):
                with self.assertRaisesRegex(ValueError, "outside standard guitar"):
                    tablature.parse_melody(passage(pitch + "1 |"))

    def test_dots_rests_comments_and_optional_version(self):
        original = (FIXTURES / "guitar-dotted.ly").read_text()
        melody = tablature.parse_melody('\\version "2.24.3"\n% comment\n' + original)
        self.assertEqual(melody.meter, "6/8")
        self.assertEqual([(event.pitch, event.duration) for event in melody.measures[0]],
                         [("e,", "4."), ("a,", "8"), ("r", "8"), ("b,", "8")])
        self.assertEqual(tablature.parse_melody(original.replace("e,4.", "e,4. % comment\n")), melody)

    def test_all_supported_durations(self):
        for denominator in (1, 2, 4, 8, 16, 32, 64):
            with self.subTest(denominator=denominator):
                melody = tablature.parse_melody(passage((f"e,{denominator} " * denominator) + "|"))
                self.assertEqual(len(melody.measures[0]), denominator)

    def test_expected_source_and_output_selection(self):
        source = (FIXTURES / "guitar-open-strings.ly").read_text()
        expected = (FIXTURES / "guitar-open-strings-both.expected.ly").read_text()
        self.assertEqual(tablature.convert_contents(source), expected)
        for representation, present, absent in (("staff", "Staff", "TabStaff"), ("tab", "TabStaff", "Staff")):
            with self.subTest(representation=representation):
                result = tablature.convert_contents(source, representation)
                self.assertIn("\\new " + present + " ", result)
                self.assertNotIn("\\new " + absent + " ", result)
        with self.assertRaisesRegex(ValueError, "output format"):
            tablature.convert_contents(source, "unknown")

    def test_unsupported_syntax_is_rejected(self):
        for body in (
            "<e, g,>1 |", "<< e,1 g,1 >> |", "e,4 a, d g |", "e,4~ e,4 r2 |",
            "e,4( a,4 d4 g4) |", "e,4\\6 a,4 d4 g4 |", "e,1\\bendAfter #2 |",
            "\\relative c' { e4 a4 d4 g4 }", "\\transpose c d { e,1 } |",
            "\\tuplet 3/2 { e,4 a,4 d4 } r2 |", "e,4. a,4.. d8 |",
            "e,4| a,4 d4 g4 |", "e,128 r1 |", "R1 |", "e#1 |", "e,1-> |",
        ):
            with self.subTest(body=body):
                with self.assertRaisesRegex(ValueError, "unsupported token"):
                    tablature.parse_melody(passage(body))
        for source in ("\\score { c'1 }", passage("e,1 |").replace("english", "deutsch"),
                       passage("e,1 |") + "\\include \"extra.ly\"", "%{ block %}\n" + passage("e,1 |")):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    tablature.parse_melody(source)

    def test_bad_measures_are_rejected(self):
        for body in ("e,4 |", "e,1 e,4 |", "e,1", "e,1 | |", "e,1 | a,4"):
            with self.subTest(body=body):
                with self.assertRaisesRegex(ValueError, "measure"):
                    tablature.parse_melody(passage(body))
        for body in ("", "r1 |"):
            with self.assertRaisesRegex(ValueError, "pitched note"):
                tablature.parse_melody(passage(body))
        with self.assertRaisesRegex(ValueError, "unsupported meter"):
            tablature.parse_melody(passage("e,1 |", "5/4"))

    def test_token_errors_keep_original_line_numbers(self):
        source = '\\language "english"\n% comment\n\\absolute {\n\\time 4/4\n<e, g,>1 |\n}\n'
        with self.assertRaisesRegex(ValueError, "line 5: unsupported token"):
            tablature.parse_melody(source)

    def test_cli_preserves_input_and_protects_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = passage("e,1 |")
            song, output = Path(directory) / "melody.ly", Path(directory) / "output.ly"
            song.write_text(source)
            result = self.run_cli(song, "--output", output, "--format", "tab")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), tablature.convert_contents(source, "tab"))
            self.assertEqual(song.read_text(), source)
            result = self.run_cli(song, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--force", result.stderr)
            result = self.run_cli(song, "--output", output, "--force")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), tablature.convert_contents(source))

    def test_invalid_input_does_not_create_or_truncate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            song, output = Path(directory) / "melody.ly", Path(directory) / "output.ly"
            song.write_text(passage("<e, g,>1 |"))
            result = self.run_cli(song, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            output.write_text("existing output\n")
            result = self.run_cli(song, "--output", output, "--force")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(output.read_text(), "existing output\n")

    def test_input_cannot_be_overwritten_even_via_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            song = Path(directory) / "melody.ly"
            song.write_text(passage("e,1 |"))
            symlink, hardlink = Path(directory) / "symlink.ly", Path(directory) / "hardlink.ly"
            symlink.symlink_to(song)
            os.link(song, hardlink)
            for output in (song, symlink, hardlink):
                with self.subTest(output=output):
                    result = self.run_cli(song, "--output", output, "--force")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("different files", result.stderr)
                    self.assertEqual(song.read_text(), passage("e,1 |"))

    def test_help_and_file_errors(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for text in ("--format", "--output", "Standard tuning", "0-20"):
            self.assertIn(text, result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            song, output = Path(directory) / "missing.ly", Path(directory) / "output.ly"
            result = self.run_cli(song, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            song.write_text(passage("e,1 |"))
            result = self.run_cli(song, "--output", Path(directory) / "absent/output.ly")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)


INSPECT_MUSIC = r'''
#(define (inspect-music label music)
   (music-map
     (lambda (event)
       (case (ly:music-property event 'name)
         ((NoteEvent RestEvent)
          (let* ((pitch (ly:music-property event 'pitch))
                 (duration (ly:music-length event)))
            (format #t "TEST-EVENT ~a ~a ~a/~a~%" label
              (if (ly:pitch? pitch) (+ 60 (ly:pitch-semitones pitch)) "rest")
              (ly:moment-main-numerator duration) (ly:moment-main-denominator duration)))))
       event)
     music))
#(define (test-tab-format context string fret)
   (format #t "TEST-TAB ~a ~a~%" string fret)
   (fret-number-tablature-format context string fret))
'''


@unittest.skipUnless(shutil.which("lilypond"), "LilyPond not installed; source tests only")
class LilyPondTablatureTests(unittest.TestCase):
    def test_native_tab_positions_and_sounding_pitch_in_all_output_formats(self):
        cases = (
            ((FIXTURES / "guitar-open-strings.ly").read_text(),
             [(40, "1/4"), (45, "1/4"), (50, "1/4"), (55, "1/4"), (59, "1/4"), (64, "1/4"), ("rest", "1/2")],
             [(6, 0), (5, 0), (4, 0), (3, 0), (2, 0), (1, 0)]),
            ((FIXTURES / "guitar-fretted.ly").read_text(),
             [(41, "1/4"), (46, "1/4"), (51, "1/4"), (56, "1/4"), (60, "1/4"), (65, "1/4"), ("rest", "1/2")],
             [(6, 1), (5, 1), (4, 1), (3, 1), (2, 1), (1, 1)]),
            ((FIXTURES / "guitar-dotted.ly").read_text(),
             [(40, "3/8"), (45, "1/8"), ("rest", "1/8"), (47, "1/8")], [(6, 0), (5, 0), (5, 2)]),
            (passage("e,4 c'''4 |", "2/4"), [(40, "1/4"), (84, "1/4")], [(6, 0), (1, 20)]),
            (passage("es4 ff4 css4 dff4 |"),
             [(53, "1/4"), (52, "1/4"), (50, "1/4"), (48, "1/4")], [(4, 3), (4, 2), (4, 0), (5, 3)]),
        )
        for index, (source, expected_events, expected_positions) in enumerate(cases):
            for representation in ("staff", "tab", "both"):
                with self.subTest(case=index, representation=representation):
                    generated = tablature.convert_contents(source, representation)
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
                            events = re.findall(rf"TEST-EVENT {label} (\S+) (\S+)", result.stdout)
                            self.assertEqual(events, [(str(pitch), duration) for pitch, duration in expected_events])
                        positions = [tuple(map(int, pair)) for pair in re.findall(r"TEST-TAB (\d+) (\d+)", result.stdout)]
                        self.assertEqual(positions, [] if representation == "staff" else expected_positions)


if __name__ == "__main__":
    unittest.main()
