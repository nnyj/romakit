"""Guess the language of CJK lyrics. Standard library only.

Checks Unicode ranges in a fixed order. Kana beats Chinese characters, since
Japanese mixes both. Hangul comes before Chinese characters, since Korean rarely
uses them alone. Chinese characters alone means Chinese.
"""
import re

KANA_REGEX = re.compile(r'[぀-ゟ゠-ヿㇰ-ㇿｦ-ﾝ]')
HANGUL_REGEX = re.compile(r'[가-힣ᄀ-ᇿ㄰-㆏ꥠ-꥿ힰ-퟿]')
HAN_REGEX = re.compile(
  r'[㐀-䶿一-鿿豈-﫿]'
  r'|[\U00020000-\U0003ffff]'  # rare traditional and variant blocks
)


def detect(text):
  """Return 'ja', 'zh', 'ko', or '' if the text has no CJK writing."""
  if KANA_REGEX.search(text):
    return 'ja'
  if HANGUL_REGEX.search(text):
    return 'ko'
  if HAN_REGEX.search(text):
    return 'zh'
  return ''


def is_cjk(text):
  """True if the text has any CJK writing."""
  return detect(text) != ''
