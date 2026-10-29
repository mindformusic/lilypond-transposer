\version "2.24.3"
\language "english"

\header {
  title = "Pop progression in C major"
  subtitle = "I | V | vi | IV"
  tagline = ##f
}

chord_sequence = \chordmode {
  c1 | g1 | a1:m | f1 |
}

music = {
  \transpose c c {
    <<
      \new ChordNames { \chord_sequence }
      \new RhythmicStaff {
        \time 4/4
        R1*4
        \bar "|."
      }
    >>
  }
}

\score {
  \music
  \layout { indent = 0 }
}
