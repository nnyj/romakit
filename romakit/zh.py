"""Chinese romanization via pypinyin (extra: zh)."""
from pypinyin import lazy_pinyin

def romanize(text):
  """Pinyin without tone marks, space separated. Other characters pass through."""
  return ' '.join(lazy_pinyin(text))

def pairs(text):
  """[(glyph, pinyin)] per character, for per-glyph karaoke on the original
  line; one hanzi is one syllable, so the mapping is 1:1."""
  return [(ch, (lazy_pinyin(ch) or [ch])[0]) for ch in text]
