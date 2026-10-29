"""Run with python -m unittest discover -s tests -v."""

import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/lilypond_transposer/generate.py"
SPEC = importlib.util.spec_from_file_location("generator", SCRIPT)
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)

# Independently spelled major scales, including both enharmonic alternatives.
SCALES = {
    "cf": "cf df ef ff gf af bf",
    "gf": "gf af bf cf df ef f",
    "df": "df ef f gf af bf c",
    "af": "af bf c df ef f g",
    "ef": "ef f g af bf c d",
    "bf": "bf c d ef f g a",
    "f": "f g a bf c d e",
    "c": "c d e f g a b",
    "g": "g a b c d e fs",
    "d": "d e fs g a b cs",
    "a": "a b cs d e fs gs",
    "e": "e fs gs a b cs ds",
    "b": "b cs ds e fs gs as",
    "fs": "fs gs as b cs ds es",
    "cs": "cs ds es fs gs as bs",
}
CHORD_DEGREES = {
    "pop": ((0, 2, 4), (4, 6, 1), (5, 0, 2), (3, 5, 0)),
    "jazz-251": ((1, 3, 5, 0), (4, 6, 1, 3), (0, 2, 4, 6), (0, 2, 4, 6)),
}


class GeneratorTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
        )

    def test_tonic_aliases(self):
        for value, expected in {
            " C ": "c", "Bb": "bf", "Bflat": "bf", "bf": "bf",
            "F#": "fs", "Fsharp": "fs", "fs": "fs", "Cb": "cf",
            "Gb": "gf", "C#": "cs",
        }.items():
            with self.subTest(value=value):
                self.assertEqual(generator.normalize_tonic(value), expected)

    def test_all_supported_keys(self):
        self.assertEqual(generator.MAJOR_KEYS, set(SCALES))
        for tonic in SCALES:
            with self.subTest(tonic=tonic):
                self.assertEqual(generator.normalize_tonic(tonic), tonic)
                self.assertIn(
                    f"\\transpose c {tonic} {{", generator.generate_score("pop", tonic),
                )

    def test_invalid_and_unsupported_tonics(self):
        for value in ("", "H", "C major", "Am", "c'", "C##", "Bbb", "../c", "E#", "Fb", "G#"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "tonic"):
                    generator.generate_score("pop", value)

    def test_unknown_progression(self):
        with self.assertRaisesRegex(ValueError, "unsupported progression"):
            generator.generate_score("blues", "c")

    def test_expected_pop_source(self):
        expected = (Path(__file__).parent / "fixtures/pop-c.ly").read_text(encoding="utf-8")
        self.assertEqual(generator.generate_score("pop", "C"), expected)

    def test_jazz_template_and_title(self):
        source = generator.generate_score("jazz-251", "Bb")
        self.assertIn('title = "Jazz ii-V-I in Bb major"', source)
        self.assertIn('subtitle = "ii7 | V7 | Imaj7 | Imaj7"', source)
        self.assertIn("d1:m7 | g1:7 | c1:maj7 | c1:maj7 |", source)
        self.assertIn("\\transpose c bf {", source)
        self.assertIn("R1*4", source)
        self.assertEqual(source, generator.generate_score("jazz-251", "Bflat"))

    def test_enharmonic_keys_are_not_collapsed(self):
        sharp = generator.generate_score("pop", "F#")
        flat = generator.generate_score("pop", "Gb")
        self.assertIn("in F# major", sharp)
        self.assertIn("\\transpose c fs {", sharp)
        self.assertIn("in Gb major", flat)
        self.assertIn("\\transpose c gf {", flat)

    def test_cli_writes_requested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "practice.ly"
            result = self.run_cli("jazz-251", "Bb", "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(output), result.stdout)
            self.assertEqual(output.read_text(), generator.generate_score("jazz-251", "Bb"))
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_cli_protects_existing_file_and_force_replaces_it(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "practice.ly"
            output.write_text("existing chart\n")
            result = self.run_cli("pop", "c", "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--force", result.stderr)
            self.assertEqual(output.read_text(), "existing chart\n")
            result = self.run_cli("pop", "c", "--output", output, "--force")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), generator.generate_score("pop", "c"))

    def test_invalid_arguments_never_write_or_truncate_output(self):
        for progression, tonic in (("blues", "C"), ("pop", "H"), ("pop", "E#")):
            with self.subTest(progression=progression, tonic=tonic):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "practice.ly"
                    result = self.run_cli(progression, tonic, "--output", output)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())
                    output.write_text("existing chart\n")
                    result = self.run_cli(progression, tonic, "--output", output, "--force")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(output.read_text(), "existing chart\n")

    def test_output_errors_are_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            for output in (Path(directory), Path(directory) / "missing/practice.ly"):
                with self.subTest(output=output):
                    result = self.run_cli("pop", "c", "--output", output, "--force")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_help_and_required_output(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for text in ("pop", "jazz-251", "--output", "--force"):
            self.assertIn(text, result.stdout)
        result = self.run_cli("pop", "c")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--output", result.stderr)


INSPECT_MUSIC = r'''
#(music-map
  (lambda (event)
    (case (ly:music-property event 'name)
      ((EventChord)
       (let ((pitches
               (filter-map
                 (lambda (note)
                   (and (eq? (ly:music-property note 'name) 'NoteEvent)
                     (let ((pitch (ly:music-property note 'pitch)))
                       (list (ly:pitch-notename pitch) (ly:pitch-alteration pitch)))))
                 (ly:music-property event 'elements)))
             (length (ly:music-length event)))
         (format #t "TEST-CHORD ~s ~a/~a~%" pitches
           (ly:moment-main-numerator length) (ly:moment-main-denominator length))))
      ((MultiMeasureRestMusic)
       (let ((length (ly:music-length event)))
         (format #t "TEST-REST ~a/~a~%"
           (ly:moment-main-numerator length) (ly:moment-main-denominator length))))
      ((ReferenceTimeSignatureMusic)
       (format #t "TEST-TIME ~s~%" (ly:music-property event 'time-signature))))
    event)
  music)
'''


@unittest.skipUnless(shutil.which("lilypond"), "LilyPond is not installed; source tests only")
class LilyPondGeneratorTests(unittest.TestCase):
    def test_chord_spellings_and_durations_in_all_supported_keys(self):
        for progression, degrees in CHORD_DEGREES.items():
            for tonic, scale in SCALES.items():
                with self.subTest(progression=progression, tonic=tonic):
                    with tempfile.TemporaryDirectory() as directory:
                        song = Path(directory) / "exercise.ly"
                        song.write_text(
                            generator.generate_score(progression, tonic) + INSPECT_MUSIC,
                            encoding="utf-8",
                        )
                        result = subprocess.run(
                            ["lilypond", "-o", str(Path(directory) / "score"), str(song)],
                            capture_output=True, text=True, timeout=60,
                        )
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertNotIn("warning:", result.stderr.lower())
                        self.assertTrue((Path(directory) / "score.pdf").is_file())
                        actual = [line for line in result.stdout.splitlines()
                                  if line.startswith("TEST-CHORD ")]
                        scale_pitches = []
                        for pitch in scale.split():
                            name = "cdefgab".index(pitch[0])
                            alteration = {"": "0", "f": "-1/2", "s": "1/2"}[pitch[1:]]
                            scale_pitches.append(f"({name} {alteration})")
                        expected = [
                            "TEST-CHORD (" + " ".join(scale_pitches[i] for i in chord) + ") 1/1"
                            for chord in degrees
                        ]
                        self.assertEqual(actual, expected)
                        self.assertEqual(re.findall(r"TEST-REST (\S+)", result.stdout), ["4/1"])
                        self.assertEqual(re.findall(r"TEST-TIME (.+)", result.stdout), ["(4 . 4)"])


if __name__ == "__main__":
    unittest.main()
