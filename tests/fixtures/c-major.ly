\version "2.24.3"
\language "english"
music = {
  \transpose c c {
    \key c \major
    c'4 d' e' f'
  }
}
\score {
  \new Staff \music
  \layout {}
}
