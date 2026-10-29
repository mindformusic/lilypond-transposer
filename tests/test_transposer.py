"""Run with python -m unittest discover -s tests -v."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/lilypond_transposer/main.py"
FIXTURES = Path(__file__).parent / "fixtures"
SPEC = importlib.util.spec_from_file_location("transposer", SCRIPT)
transposer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transposer)


class TransposerTests(unittest.TestCase):
    def test_key_normalization(self):
        for value, expected in {
            " C ": "c", "Bb": "bf", "F#": "fs", "Aflat": "af",
            "Gsharp": "gs", "ef": "ef", "css": "css", "Bbb": "bff",
        }.items():
            with self.subTest(value=value):
                self.assertEqual(transposer.normalize_key(value), expected)

    def test_invalid_keys(self):
        for value in ("", "h", "c major", "c'", "bflatsharp", "../d", "c###"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid target key"):
                    transposer.normalize_key(value)

    def test_fixture_transformations(self):
        for fixture, source, key in (
            ("c-major.ly", "c", "d"),
            ("f-major.ly", "f", "g"),
            ("c-major.ly", "c", "Bb"),
        ):
            with self.subTest(fixture=fixture, key=key):
                original = (FIXTURES / fixture).read_text()
                expected = original.replace(
                    f"\\transpose {source} {source}",
                    f"\\transpose {source} {transposer.normalize_key(key)}",
                )
                self.assertEqual(transposer.transpose_contents(original, key), expected)

    def test_octave_and_existing_reference_pitches(self):
        original = "  \\transpose f, bf' { % keep this comment\n  \\key f \\major\n}\n"
        for octave, suffix in ((None, ""), ("up", "'"), ("down", ",")):
            with self.subTest(octave=octave):
                self.assertEqual(
                    transposer.transpose_contents(original, "g", octave),
                    original.replace("bf'", "g" + suffix),
                )

    def test_multiple_transpose_statements(self):
        original = "\\transpose c c { c'4 }\n\\transpose f f { f'4 }\n"
        self.assertEqual(
            transposer.transpose_contents(original, "d"),
            "\\transpose c d { c'4 }\n\\transpose f d { f'4 }\n",
        )

    def test_comments_and_line_endings_are_preserved(self):
        original = "% \\transpose h h { ignored }\r\n\t\\transpose c c { c'4 } % comment\r\n"
        self.assertEqual(
            transposer.transpose_contents(original, "d"),
            original.replace("\\transpose c c", "\\transpose c d"),
        )

    def test_missing_or_malformed_transpose(self):
        for original in (
            "\\score { c'4 }\n", "% \\transpose c c { c'4 }\n",
            "\\transpose\n", "\\transpose c {\n", "\\transpose h c {\n",
            "\\transpose c h {\n", "\\transpose c c\n{\n",
            "\\transpose c c { c'4 }\n\\transpose c {\n",
        ):
            with self.subTest(original=original):
                with self.assertRaisesRegex(ValueError, "transpose"):
                    transposer.transpose_contents(original, "d")

    def test_lyrics_toggle(self):
        original = "\\transpose c c { c'4 }\n\\addlyrics {\n  la\n}\n"
        without = transposer.transpose_contents(original, "d")
        self.assertEqual(
            without,
            "\\transpose c d { c'4 }\n% \\addlyrics {\n%   la\n% }\n",
        )
        restored = transposer.transpose_contents(without, "d", lyrics="on")
        self.assertEqual(restored, "\\transpose c d { c'4 }\n\\addlyrics {\nla\n}\n")

    def test_cli_creates_output_without_changing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            song = Path(directory) / "song.ly"
            original = (FIXTURES / "c-major.ly").read_text()
            song.write_text(original)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(song), "Bb", "--octave", "down", "--lyrics", "on"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = song.with_name("song-bf.ly")
            self.assertIn(str(output), result.stdout)
            self.assertEqual(song.read_text(), original)
            self.assertEqual(output.read_text(), original.replace("\\transpose c c", "\\transpose c bf,"))

    def test_cli_errors_do_not_write_output(self):
        cases = (
            ("\\score { c'4 }", "d", "no supported"),
            ("\\transpose c h {", "d", "line 1: malformed"),
            ("\\transpose c c {", "H", "invalid target key"),
        )
        for contents, key, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                song = Path(directory) / "song.ly"
                song.write_text(contents)
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), str(song), key], capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(list(Path(directory).iterdir()), [song])

    def test_invalid_input_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            song = Path(directory) / "song.ly"
            output = Path(directory) / "song-d.ly"
            song.write_text("\\transpose c h {\n")
            output.write_text("existing output\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(song), "d"], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "existing output\n")

    def test_missing_input_file_is_a_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            song = Path(directory) / "missing.ly"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(song), "d"], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing.ly", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


# Inspect LilyPond's actual transposed music, not just the rewritten source.
INSPECT_MUSIC = r'''
#(music-map
  (lambda (event)
    (case (ly:music-property event 'name)
      ((NoteEvent)
       (let ((pitch (ly:music-property event 'pitch)))
         (format #t "TEST-NOTE ~s~%"
           (list (ly:pitch-octave pitch) (ly:pitch-notename pitch)
                 (ly:pitch-alteration pitch)))))
      ((KeyChangeEvent)
       (format #t "TEST-KEY ~s ~s~%"
         (ly:pitch-notename (ly:music-property event 'tonic))
         (map (lambda (n)
                (assoc-get n (ly:music-property event 'pitch-alist) 0))
              (iota 7)))))
    event)
  music)
'''


@unittest.skipUnless(shutil.which("lilypond"), "LilyPond is not installed; source tests only")
class LilyPondTests(unittest.TestCase):
    def test_transposed_notes_and_key_signatures(self):
        cases = (
            ("c-major.ly", "d", None, "1 (1/2 0 0 1/2 0 0 0)",
             ["(0 1 0)", "(0 2 0)", "(0 3 1/2)", "(0 4 0)"]),
            ("f-major.ly", "g", None, "4 (0 0 0 1/2 0 0 0)",
             ["(0 4 0)", "(0 5 0)", "(0 6 0)", "(1 0 0)"]),
            ("c-major.ly", "Bb", None, "6 (0 0 -1/2 0 0 0 -1/2)",
             ["(0 6 -1/2)", "(1 0 0)", "(1 1 0)", "(1 2 -1/2)"]),
            ("c-major.ly", "d", "up", "1 (1/2 0 0 1/2 0 0 0)",
             ["(1 1 0)", "(1 2 0)", "(1 3 1/2)", "(1 4 0)"]),
            ("c-major.ly", "d", "down", "1 (1/2 0 0 1/2 0 0 0)",
             ["(-1 1 0)", "(-1 2 0)", "(-1 3 1/2)", "(-1 4 0)"]),
        )
        for fixture, key, octave, expected_key, expected_notes in cases:
            with self.subTest(fixture=fixture, key=key, octave=octave):
                contents = transposer.transpose_contents((FIXTURES / fixture).read_text(), key, octave)
                with tempfile.TemporaryDirectory() as directory:
                    song = Path(directory) / "test.ly"
                    song.write_text(contents + INSPECT_MUSIC)
                    result = subprocess.run(
                        ["lilypond", "-o", str(Path(directory) / "score"), str(song)],
                        capture_output=True, text=True, timeout=60,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue((Path(directory) / "score.pdf").is_file())
                    keys = [line.removeprefix("TEST-KEY ") for line in result.stdout.splitlines()
                            if line.startswith("TEST-KEY ")]
                    notes = [line.removeprefix("TEST-NOTE ") for line in result.stdout.splitlines()
                             if line.startswith("TEST-NOTE ")]
                    self.assertEqual(keys, [expected_key])
                    self.assertEqual(notes, expected_notes)


if __name__ == "__main__":
    unittest.main()
