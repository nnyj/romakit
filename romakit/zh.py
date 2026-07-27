"""Chinese romanization via pypinyin (extra: zh)."""
from pypinyin import lazy_pinyin


def romanize(text):
  """Pinyin without tone marks, space separated. Other characters pass through."""
  return ' '.join(lazy_pinyin(text))
