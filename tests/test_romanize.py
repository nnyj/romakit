"""Language dispatch for romanize()."""
import pytest

from romakit import mora, norm_lang, pairs, romanize

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

def test_pairs_japanese_are_per_word():
  # a multi-glyph word stays one unit, romaji trimmed of spacing
  pr = pairs('空に浮かぶ月', lang='jp')
  assert ('浮かぶ', 'ukabu') in pr
  assert [s for s, _ in pr] == ['空', 'に', '浮かぶ', '月']

def test_pairs_chinese_are_per_glyph():
  pytest.importorskip('pypinyin')
  assert pairs('你好', lang='cn') == [('你', 'ni'), ('好', 'hao')]

def test_pairs_non_cjk_empty():
  assert tuple(pairs('hello', lang='jp')) == ()

def test_mora_splits_per_kana():
  # each kana is one unit (浮 -> u, か -> ka), a following vowel does not merge
  assert [u.strip() for u in mora('浮かぶ', capitalize=False)] == ['u', 'ka', 'bu']
  assert [u.strip() for u in mora('返る', capitalize=False)] == ['ka', 'e', 'ru']

def test_mora_keeps_embedded_foreign_word_whole():
  # a word with no kana reading has no mora to split, so it stays one unit
  assert 'frail' in [u.strip() for u in mora('疑問はfrail', capitalize=False)]

def test_mora_sokuon_and_n():
  # っ leads the next mora (kko), ん is its own
  assert [u.strip() for u in mora('しんけん', capitalize=False)] == ['shi', 'n', 'ke', 'n']
  assert [u.strip() for u in mora('がっき', capitalize=False)] == ['ga', 'kki']
