"""Romanize CJK text, and guess which language it is.

detect needs nothing extra. Each romanizer needs its own package (jp: cutlet,
zh: pypinyin, ko: korean-romanizer), so they import lazily and
`from romakit import detect` works without installing them.
"""
from .detect import detect, is_cjk

__all__ = ["detect", "is_cjk", "has_japanese", "romanize", "LANGS", "norm_lang"]

# command line codes, mapped to the codes detect() returns.
# 'auto' means guess per text.
LANGS = ("auto", "jp", "cn", "kr")
_LANG_MAP = {"jp": "ja", "cn": "zh", "kr": "ko",
             "ja": "ja", "zh": "zh", "ko": "ko",
             "auto": "", "": ""}

def norm_lang(lang):
  """'jp'/'ja' -> 'ja', 'cn'/'zh' -> 'zh', 'kr'/'ko' -> 'ko', 'auto'/'' -> ''."""
  key = (lang or "").lower()
  if key not in _LANG_MAP:
    raise ValueError(f"unknown lang {lang!r}, expected one of {LANGS}")
  return _LANG_MAP[key]

def romanize(text, lang="auto", **jp_kw):
  """Romanize CJK text. Other text passes through unchanged.

  lang='auto' guesses, falling back to Japanese when no CJK writing is found
  (jp.romanize then returns the text as is).
  jp_kw (capitalize, title) goes to jp.romanize only; zh and ko take no options.
  """
  loc = norm_lang(lang) or detect(text)
  if loc == "zh":
    from . import zh
    return zh.romanize(text)
  if loc == "ko":
    from . import ko
    return ko.romanize(text)
  from . import jp
  return jp.romanize(text, **jp_kw)

def __getattr__(name):
  if name == "has_japanese":
    from . import jp
    return jp.has_japanese
  raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
