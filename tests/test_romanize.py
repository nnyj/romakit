"""Language dispatch for romanize()."""
import pytest

from romakit import norm_lang, romanize

def test_norm_lang():
  assert norm_lang('jp') == 'ja'
  assert norm_lang('cn') == 'zh'
  assert norm_lang('KR') == 'ko'
  assert norm_lang('auto') == ''
  assert norm_lang(None) == ''
  with pytest.raises(ValueError):
    norm_lang('xx')

def test_auto_kana_to_jp():
  assert romanize('こんにちは').lower().startswith('kon')

def test_auto_hangul_to_kr():
  pytest.importorskip('korean_romanizer')
  assert romanize('안녕하세요').lower().startswith('annyeong')

def test_auto_han_only_follows_detector():
  pytest.importorskip('pypinyin')
  assert romanize('你好') == 'ni hao'  # detector says zh

def test_explicit_lang_overrides_detector():
  assert romanize('漢字', lang='jp').lower().startswith('kanji')

def test_auto_non_cjk_passthrough():
  assert romanize('hello world') == 'hello world'
