"""Korean romanization via korean-romanizer (extra: ko)."""
from korean_romanizer.romanizer import Romanizer


def romanize(text):
  """Revised Romanization of Korean. Non-hangul characters pass through."""
  return Romanizer(text).romanize()
