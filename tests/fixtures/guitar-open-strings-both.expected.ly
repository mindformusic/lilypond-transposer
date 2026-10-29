\version "2.24.3"
\language "english"
% Standard tuning: string 1 = E4, 2 = B3, 3 = G3, 4 = D3, 5 = A2, 6 = E2.
% Sounding pitches; guitar staff uses an octave-down treble clef.

staff_music = \absolute {
  \clef "treble_8"
  \time 4/4
  e,4 a,4 d4 g4 |
  b4 e'4 r2 |
  \bar "|."
}

tab_music = \absolute {
  \tabFullNotation
  \time 4/4
  e,4\6 a,4\5 d4\4 g4\3 |
  b4\2 e'4\1 r2 |
  \bar "|."
}

\score {
  <<
    \new Staff { \staff_music }
    \new TabStaff \with { stringTunings = #guitar-tuning } { \tab_music }
  >>
  \layout {}
}
