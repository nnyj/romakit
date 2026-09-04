"""Korean romanization via korean-romanizer (extra: ko)."""
from korean_romanizer.romanizer import Romanizer

def romanize(text):
  """Revised Romanization of Korean. Non-hangul characters pass through."""
  return Romanizer(text).romanize()

def pairs(text):
  """[(syllable block, roman)] per character, for per-glyph karaoke on the
  original line; a hangul block romanizes on its own."""
  return [(ch, Romanizer(ch).romanize()) for ch in text]
