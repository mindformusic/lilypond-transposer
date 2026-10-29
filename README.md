# lilypond-transposer
A simple CLI sheet music transposer that uses LilyPond.

# Background
This code was featured in a YouTube video talking about how valuable LilyPond could be to public music education:

# Guitar tablature
See [guitar staff and tablature output](docs/guitar-tablature.md) for the separate CLI that converts supported single-note melodies or explicit string/fret data.

# Usage
This code is (mostly) designed for transposing Jazz lead sheets that use both chords and melody although it can do other things. In order for the transposition to work you have to wrap the LilyPond code in the \transpose block:

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

Then using the command line:
```
python {filename} {lilypond_file} {desired_key} --octave {up or down} --lyrics {on or off}
```

So for example:
```
python lilypond-transposer.py stardust.ly d --octave down --lyrics on
```

# TODO
1.) Transpose the KEY SIGNATURE along with the actual melody and notes
