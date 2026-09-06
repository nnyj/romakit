from romakit import detect, is_cjk

def test_kana_means_ja():
  assert detect('ひらがな') == 'ja'
  assert detect('ｶﾀｶﾅ') == 'ja'           # halfwidth katakana
  assert detect('残酷な天使のテーゼ') == 'ja'  # kana wins over han

def test_hangul_means_ko():
  assert detect('안녕하세요') == 'ko'
  assert detect('ㄱㄴㄷ') == 'ko'

def test_bare_han_falls_to_zh():
  assert detect('我爱你') == 'zh'
  assert detect('㐀') == 'zh'   # extension A, outside the common block

def test_non_cjk():
  assert detect('hello world') == ''
  assert detect('') == ''

def test_is_cjk():
  assert is_cjk('さくら')
  assert is_cjk('漢字')
  assert not is_cjk('abc 123')
