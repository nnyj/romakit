"""Japanese to romaji using cutlet, tuned for song lyrics.

Adds on top of plain cutlet:
- jp_words.tsv: fixed readings merged into cutlet's table, plus text fixes run
  before MeCab
- spacing rewritten where human romaji glues or splits differently (nda, demo)
- small kana written as a doubled vowel (ねぇ -> nee)
- lone romanized n glued back to the word before it (mie n -> mien)
- furigana used as the reading
- kun'yomi over on'yomi where MeCab misleans

On that last point: MeCab is trained on normal text, so a kanji standing alone
usually gets on'yomi (jutsu, kuu, jin) while lyrics want kun'yomi (sube, sora,
hito). _path_penalty scores MeCab's n-best parses, pushing down those on'yomi
picks and junk parses.

Unsolved: two kun'yomi candidates (soba vs gawa) give no signal, so those words
go in the data file; ateji needs furigana or the audio.

Every word entry and spacing rule here is measured net-positive against human
romaji on a lyric corpus.

Terms are used bare here; see README Glossary.
"""
import warnings
from functools import lru_cache
from pathlib import Path

import cutlet
import jaconv
import regex as re

# --- word overrides ---


def _load_words():
  """(readings, pre-MeCab substitutions) from jp_words.tsv; see its header."""
  readings, subs = {}, {}
  for line in Path(__file__).with_name('jp_words.tsv').read_text('utf-8').splitlines():
    if line and not line.startswith('#'):
      kind, key, value = line.split('\t')[:3]
      (readings if kind == 'r' else subs)[key] = value
  return readings, subs


# EXCEPTIONS is a fixed reading, applied only when MeCab splits the word off as a
# whole token, so compounds like 内側/台風/私立 are untouched. It covers what the
# re-ranker cannot see (both readings native) and words unidic gets wrong.
# PRE_SUB fixes words unidic splits into several tokens, which EXCEPTIONS then
# cannot reach (勿れ splits into 勿+れ).
EXCEPTIONS, PRE_SUB = _load_words()
# Same idea, but bare word only: any word before it turns the override off.
# 性 alone is saga, as an ending (可能性) sei. 的 alone is the noun mato
# (的外れ matohazure), as an ending (大人的) teki. 度 alone is tabi (この度),
# after a number the counter do (一度). 生 alone is sei, unidic says nama.
POS_EXCEPTIONS = {('性', '名詞'): 'saga', ('的', '接尾辞'): 'mato',
                  ('度', '名詞'): 'tabi', ('生', '名詞'): 'sei'}
NO_EXC_AFTER = ('名詞', '形状詞', '接頭辞', '接尾辞', '代名詞')

# --- patterns ---

JP_REGEX = re.compile(r'[\p{IsHira}\p{IsKatakana}\p{IsHan}]')
# Inline furigana: kanji, then the kana reading in brackets, as in 外(はず)して.
# The kana covers the whole kanji group before it, so taking all of them is safe
# (大好(だいす)き). Brackets holding non-kana are left alone.
# Drop brackets, keep kanji: MeCab needs the kanji to split words, and the kana is
# stored as that word's reading. Writing kana into the text breaks the split
# (澄んだ -> すんだ).
FURIGANA_REGEX = re.compile(r'(\p{IsHan}+)[(（]([\p{IsHira}\p{IsKatakana}ー]+)[)）]')
KANA_ONLY_REGEX = re.compile(r'[\p{IsHira}\p{IsKatakana}ー]+')
# A digit plus its counter is one token (1人), so the reading comes out "1ひとり".
# The kana already says the number, so drop the digits.
LEADING_DIGITS_REGEX = re.compile(r'^\d+')
# a lone romanized ん, as in "mie n da"; can also hit English "rock n roll" (fine)
FLOATING_N_REGEX = re.compile(r'(?<=[a-zA-Z]) n\b')
KANJI_REGEX = re.compile(r'\p{IsHan}')
kanji_char = KANJI_REGEX.match
NBEST = 4  # how many MeCab parses to score
# Single kanji where lyrics want kun'yomi over MeCab's on'yomi
# pick (術: jutsu -> sube). Fixed list on purpose: a blanket rule breaks words
# where on'yomi is the normal reading (気 ki, 度 do, 一 ichi).
KUN_PREFERRED = set(
  '空宙人君術鳥音月時刻詩理言心中日手道事声星街歌体色'
  '今名光数他力外車形種船眼海次赤'
  '金家年傷水雨鋼耳所灯波藍橋'
  '枝角味鬼鼻土物絆町故傘罪輪世刀')
# Left out on purpose: 愛 (would become mana), 度/一/二/三/四/気/曲 (on'yomi
# reading is the normal word), 方/様/後/間/下/傍/悪/強/真/笑/生/彩/刃/直/御
# (sentence-dependent, let MeCab decide).
# Single kanji tagged as a person name (創 -> Hajime, 昂 -> Noboru) is also not
# punished: that hurts real names (藤女, 川口進, 篤). Those go in EXCEPTIONS.

# --- zh glyph repair ---

# Lyric sites sometimes store Japanese songs with Chinese character shapes
# (乐谱 for 楽譜); cutlet prints those as '?'. Fix via opencc, simplified ->
# traditional -> Japanese, one kanji group at a time so the surrounding word can
# decide (发型 -> 髪型 but 头发 -> 頭髪).
# Convert a group only if it holds a character opencc changes AND that is not
# valid Japanese. JP_SAFE lists characters that are normal Japanese even though
# opencc would change them (机/叶/里/干/后/洒); without it opencc rewrites correct
# Japanese (回路 -> 迴路, 洒落 -> 灑落). Inside an already broken group, JP_SAFE
# characters do get converted (电视机 -> 電視機). kyuujitai (樂/氣/髮)
# stay out of JP_SAFE since they must convert. Chinese-only grammar characters
# (的/这/你) are untouched, so broken Chinese stays visibly broken instead of
# becoming plausible nonsense.
JP_SAFE = frozenset(
  '丑云亙侠俣俱凄准凛凶剥占厘厦厨厩叶后咸堯岩峯嶽巖干庄廣征怜惧戯托据搜携摑斗'
  '晄晒朴机栖槇檜洒淀澤焰燈猪瑶眞祿禰禱穰筑繡繫聯肴萊萠萬蔣薮藏藝蠟踪遙郁醬采'
  '里雇鷗龍渚琢祐禎'
  '蝉躯痒咤')  # shinjitai opencc misses (gives 蟬/軀/癢/吒)
HAN_RUN_REGEX = re.compile(r'\p{IsHan}+')

try:
  import opencc
  _s2t = opencc.OpenCC('s2t')
  _t2jp = opencc.OpenCC('t2jp')
except Exception:  # optional package, like the other jp extras
  _s2t = _t2jp = None
  warnings.warn('opencc missing: zh-simplified lyric glyphs stay unromanizable', stacklevel=2)


@lru_cache(maxsize=4096)
def _is_zh_only(char):
  """True if opencc changes this character and it is not valid Japanese."""
  return char not in JP_SAFE and _t2jp.convert(_s2t.convert(char)) != char


def _repair_run(match):
  run = match.group()
  if not any(_is_zh_only(c) for c in run):
    return run
  fixed = _t2jp.convert(_s2t.convert(run))
  if len(fixed) != len(run):
    return fixed
  # opencc sees the whole group for word context, but keep its output only for
  # characters needing repair; otherwise it rewrites correct kanji (背负 -> 揹負)
  return ''.join(f if _is_zh_only(c) else c for c, f in zip(run, fixed))


def _zh_to_shinjitai(text):
  """zh and kyuujitai forms -> shinjitai, one kanji group at a time.

  Fully Japanese groups are left alone.
  """
  if _s2t is None:
    return text
  return HAN_RUN_REGEX.sub(_repair_run, text)


# --- text fixes applied before MeCab ---

# Replacements are katakana where the target is a reading: hiragana gets split
# again (ねんがっぴ -> "nen gap pi"), katakana stays one unknown word.
# Left broken: 空回って/空回る come out "sora mawatte" (空回り is fine). Every kana
# spelling of karamawa splits into カラ+マワ, reading worse than the original.
# A key ending in kanji may carry its own furigana (三日月(みかづき)). Replacing the
# kanji there breaks FURIGANA_REGEX and leaves the brackets in the output, so skip
# the replacement and let the furigana win.
_RUBY_AHEAD = r'(?![(（][\p{IsHira}\p{IsKatakana}ー]+[)）])'
_PRE_SUB_RULES = [(re.compile(src + (_RUBY_AHEAD if kanji_char(src[-1]) else '')), dst)
                  for src, dst in PRE_SUB.items()]

# unidic gives a digit no reading at all, so cutlet prints it ("3ji"), while it
# reads kanji numerals with the right counter phonology (三時 sanji, 一分 ippun,
# 二つ futatsu). So digits are rewritten before tagging. Ceiling: four digits,
# enough for counters and years; a longer run stays as it is. A bare 0 is left
# for the word data, which reads it zero rather than the counter form rei.
KANJI_DIGITS = '〇一二三四五六七八九'
KANJI_UNITS = ((1000, '千'), (100, '百'), (10, '十'))
DIGIT_RUN_REGEX = re.compile(r'\d+')


def _kanji_number(match):
  n = int(match.group())
  if not n or len(match.group()) > 4:
    return match.group()
  out = []
  for value, unit in KANJI_UNITS:
    count, n = divmod(n, value)
    if count:
      out.append((KANJI_DIGITS[count] if count > 1 else '') + unit)
  return ''.join(out) + (KANJI_DIGITS[n] if n else '')


# --- furigana handling ---

class _Node:
  """Copy of a fugashi word, with leading spacing taken from the source text."""
  __slots__ = ('surface', 'feature', 'is_unk', 'char_type', 'white_space', 'ruby', 'pos_exc')


def _strip_ruby(text):
  """Remove furigana brackets, keep the kanji.

  Returns (text, [(start, end, kana)]) with positions in the new text.
  """
  parts = []
  spans = []
  pos = 0
  length = 0
  for m in FURIGANA_REGEX.finditer(text):
    parts.append(text[pos:m.start()])
    length += m.start() - pos
    kanji = m.group(1)
    parts.append(kanji)
    spans.append((length, length + len(kanji), m.group(2)))
    length += len(kanji)
    pos = m.end()
  if not spans:
    return text, spans
  parts.append(text[pos:])
  return ''.join(parts), spans


def _token_ruby(surface, start, spans):
  """Reading for one word, furigana kana swapped in for the kanji it covers.

  Returns (reading, span_indexes), or (None, ()) if no furigana fits this word.
  """
  end = start + len(surface)
  hits = [(i, s) for i, s in enumerate(spans) if s[0] < end and s[1] > start]
  if not hits:
    return None, ()
  out = []
  cur = start
  for _, (s, e, kana) in hits:
    if s < start or e > end:  # furigana crosses a word boundary, caller retries
      return None, ()
    out.append(surface[cur - start:s - start])
    out.append(kana)
    cur = e
  out.append(surface[cur - start:])
  reading = LEADING_DIGITS_REGEX.sub('', ''.join(out))
  # kana only: any other character is missing from cutlet's kana table and raises
  # (1人(ひとり) would give KeyError '1')
  if not KANA_ONLY_REGEX.fullmatch(reading):
    return None, ()
  return reading, [i for i, _ in hits]


def _sub_spans(text, spans, missed):
  """Write kana into the text for furigana no word could take, keep the rest."""
  parts = []
  kept = []
  pos = 0
  length = 0
  for i, (s, e, kana) in enumerate(spans):
    parts.append(text[pos:s])
    length += s - pos
    if i in missed:
      parts.append(kana)
      length += len(kana)
    else:
      parts.append(text[s:e])
      kept.append((length, length + e - s, kana))
      length += e - s
    pos = e
  parts.append(text[pos:])
  return ''.join(parts), kept


def _wrap_nodes(path, text, spans, used):
  nodes = []
  pos = 0
  for w in path:
    idx = text.find(w.surface, pos)
    n = _Node()
    n.ruby = None
    if spans and idx >= 0:
      n.ruby, hit = _token_ruby(w.surface, idx, spans)
      used.update(hit)
    n.surface = w.surface
    n.feature = w.feature
    n.is_unk = w.is_unk
    n.char_type = w.char_type
    n.white_space = w.white_space if idx < 0 else text[pos:idx] if idx > pos else ''
    nodes.append(n)
    if idx >= 0:
      pos = idx + len(w.surface)
  for i, n in enumerate(nodes):
    nxt = nodes[i + 1] if i + 1 < len(nodes) else None
    prev = nodes[i - 1] if i > 0 else None
    n.pos_exc = (None if prev is not None and prev.feature.pos1 in NO_EXC_AFTER
                 else POS_EXCEPTIONS.get((n.surface, n.feature.pos1)))
    # 理不尽 splits into 理+不尽, and 理 is KUN_PREFERRED, so scoring picks kotowari
    if n.surface == '理' and nxt is not None and nxt.surface == '不尽':
      n.pos_exc = 'ri'
  return nodes


# --- scoring MeCab's candidate parses ---

def _path_penalty(path):
  """Score one MeCab parse of a line; lower score wins."""
  penalty = 0
  for i, w in enumerate(path):
    f = w.feature
    # shortened ん read as a filler sound (分から+ん should beat 分+から+ん)
    if w.surface == 'ん' and f.pos2 == 'フィラー':
      penalty += 2
    # a single kanji from KUN_PREFERRED given its on'yomi
    if (len(w.surface) == 1 and w.surface in KUN_PREFERRED
        and f.pos1 == '名詞' and f.goshu == '漢'):
      prev = path[i - 1] if i > 0 else None
      # Skip after a number (一日 ichi-nichi) or noun (歩道+橋 hodoukyou): a split
      # compound keeps on'yomi in both halves. The word after
      # is not checked: that fixed 理+不尽 but broke 星 空 / 内 瑞 / 学 過, since
      # MeCab sees two nouns side by side with or without a space in the lyric.
      if not (prev is not None and (prev.feature.pos2 == '数詞'
              or prev.surface.isdigit() or prev.feature.pos1 == '名詞')):
        penalty += 1
    # kanji read as a foreign name (汗 -> ハン, Khan): unidic keeps those entries
    # for Chinese and Mongolian names, lyrics want the Japanese word. EXCEPTIONS
    # words are skipped: 刹那's entry is the Sanskrit "ksana", so this rule pushed
    # down the correct parse and the override never ran.
    # kanji_char first: it rejects the kana majority without running the run match
    if (kanji_char(w.surface) and HAN_RUN_REGEX.fullmatch(w.surface)
        and w.surface not in EXCEPTIONS and cutlet.has_foreign_lemma(w)):
      penalty += 2
    # a lone て tagged as the particle って: impossible, って needs its っ, so
    # 目眩し+て must not be read as 目眩し + って
    if w.surface == 'て' and f.lemma == 'って':
      penalty += 1
    # 脅かす has two kun'yomi: with an object it is "threaten", obiyakasu
    # (命を脅かした); alone it is "scare", odokasu (脅かして). を before it marks
    # the object.
    if f.lemma == '脅かす':
      obj_marked = i > 0 and path[i - 1].surface == 'を'
      wrong = ('オドカ' if obj_marked else 'オビヤカ')
      if f.kana.startswith(wrong):
        penalty += 1
    # 目眩+し is a wrong split of 目眩し mekuramashi; the noun memai takes が or に
    if (w.surface == '目眩' and f.kana == 'メマイ'
        and i + 1 < len(path) and path[i + 1].surface == 'し'):
      penalty += 1
    # a word ending with nothing in front is a wrong parse (鏡 starting a line ->
    # kyou); a real ending (世界+中 juu) has a noun before it
    if (len(w.surface) == 1 and kanji_char(w.surface) and f.pos1 == '接尾辞'
        and (i == 0 or path[i - 1].feature.pos1 not in ('名詞', '接尾辞', '代名詞'))):
      penalty += 1
    # command form ending in -え read as noun + exclamation え (歌え -> uta e)
    if (w.surface == 'え' and f.pos1 == '感動詞' and i > 0
        and path[i - 1].feature.pos1 == '名詞'):
      penalty += 1
    # 何: nan before だ/で/と and counters (何度 nando), nani elsewhere (何を nani wo)
    if w.surface == '何' and f.kana in ('ナニ', 'ナン'):
      nxt = path[i + 1] if i + 1 < len(path) else None
      nan_ctx = nxt is not None and (
        nxt.feature.pos2 == '助数詞' or nxt.feature.pos3 == '助数詞可能'
        or nxt.feature.pos1 == '接尾辞'
        or nxt.surface[:1] in ('だ', 'で', 'と', 'な'))
      if f.kana == ('ナニ' if nan_ctx else 'ナン'):
        penalty += 1
  return penalty


# 一 plus a counter geminates before p/k/s/t
# (一歩 ippo, 一回 ikkai). unidic stores only some as whole words (一杯 ippai) and
# splits the rest into 一 + counter.
GEMINATE_HEADS = 'pkst'


def _geminate_ichi(words, tokens):
  """Merge ichi + counter into the doubled-consonant form (ichi po -> ippo)."""
  for i, w in enumerate(words[:-1]):
    if w.surface != '一' or tokens[i].surface.lower() != 'ichi':
      continue
    nxt = words[i + 1]
    head = tokens[i + 1].surface[:1].lower()
    # some counters read 一 as hito (hitotsubu); the 'ichi' check above skips them
    if (head not in GEMINATE_HEADS or len(nxt.surface) != 1
        or not kanji_char(nxt.surface) or nxt.feature.pos1 not in ('名詞', '接尾辞')):
      continue
    tokens[i].surface = ('I' if tokens[i].surface[0] == 'I' else 'i') + head
    tokens[i].space = False


# --- spacing ---

# cutlet spaces on part of speech; human romaji writes some clusters solid and
# some of cutlet's clusters apart. Rules below are keyed on part of speech where
# the class is closed (quoting って, indefinite か, fillers); the table holds the
# clusters left over, keyed on the surface pair. Ceiling: pairs only, so a
# three-word cluster needs each step listed (な+ん and ん+だ give nanda).
ATTACH = {
  'いつ': ('し', 'しか', 'も'), 'どう': ('し', 'しよう', 'も', 'やら'),
  'なん': ('だ', 'で', 'と'), '何': ('だ', 'で', 'と'), 'か': ('い', 'な', 'も'),
  'な': ('の', 'ん'), 'ん': ('だ', 'で'), 'と': ('か', 'も'), 'だ': ('か',),
  'で': ('も',), 'も': ('か',), 'こう': ('し',), 'そ': ('し',), 'や': ('し',),
  'もし': ('も',), 'それ': ('で',), 'たく': ('ない',), 'て': ('たい',),
}
# particles that always lean on the word before them (一人きり, 少しずつ)
ATTACH_SUFFIX = ('きり', 'ずつ')
# Conjunctive particles humans keep attached; the rest (から, けど, し, が, ながら)
# take a space, except after the copula だ (dakara, dakedo).
ATTACH_CONJ = ('て', 'で', 'ば', 'たり', 'つつ', 'ちゃ', 'たって')
# Auxiliaries cutlet glues to the verb but humans write apart
SPLIT_AUX = ('なら', 'だろ', 'だろう', 'でしょ', 'でしょう')
VOWEL_KANA = 'ぁあぃいぅうぇえぉお'
SMALL_VOWELS = 'ぁぃぅぇぉ'
KATAKANA_PAIR_REGEX = re.compile(r'[\p{IsKatakana}]{2}')


def _attach(prev, cur, prev_roma, roma):
  """True to glue this word to the one before it, False to space, None to leave."""
  a, b = prev.surface, cur.surface
  pa, pb = prev.feature, cur.feature
  # って quotes the word before it and stands apart, except on the copula
  # (nandatte, sou datte); the -te form keeps its own particle (kite tte)
  if b == 'って':
    return a in ('だ', 'な')
  # も after a -te form is the concessive "even if" and takes a space (tonde mo),
  # unlike the で of だ (demo)
  if b == 'も' and pa.pos2 == '接続助詞':
    return False
  if pb.pos2 == '接続助詞':
    return b in ATTACH_CONJ or a == 'だ'
  if b in SPLIT_AUX and pb.pos1 == '助動詞':
    return False
  if b in ATTACH.get(a, ()) or b in ATTACH_SUFFIX:
    return True
  # か on a question word makes one indefinite word (dareka, itsuka, doushika).
  # そうか is the exception: there か is the question, not part of the word.
  if b == 'か' and pb.pos2 == '副助詞':
    return (pa.pos1 in ('代名詞', '副詞') and a != 'そう') or pa.pos2 == '副助詞'
  # a helper verb keeps the verb it modifies (歩き出す arukidasu, 泣いたり naitari)
  if pa.pos1 == '動詞' and (pb.pos2 == '非自立可能' or b == 'たり'):
    return True
  # そう "looks like" leans on the word it grades (消えそう kiesou, 楽しそう
  # tanoshisou); as an adverb it is a word of its own (sou sa, sou da)
  if b == 'そう' and pb.pos2 == '助動詞語幹':
    return pa.pos1 in ('動詞', '形容詞', '助動詞')
  if b == 'さ' and pb.pos1 == '接尾辞':
    return pa.pos1 not in ('名詞', '形状詞')  # 悲しさ kanashisa, but sou sa
  # っ cannot start or end a word on its own (ずっと, ぎゅっと)
  if b[0] == 'っ' or a[-1] == 'っ':
    return True
  if pa.pos2 == '数詞' and pb.pos1 == '名詞':
    return True  # 何度 nando, 一度 ichido
  # a two-kanji noun with a single kanji after it is one compound MeCab split
  # (交差+点 kousaten, 蜃気+楼 shinkirou, 違和+感 iwakan)
  if (pa.pos2 == pb.pos2 == '普通名詞' and len(a) == 2 and len(b) == 1
      and HAN_RUN_REGEX.fullmatch(a) and kanji_char(b)):
    return True
  # a repeated cry is one drawn-out word (ああ ああ -> aaaa), but a repeated word
  # is two (hora hora); two-mora katakana doubles as one word (baibai, dokidoki)
  if a == b:
    if pa.pos1 == '感動詞':
      return all(c in VOWEL_KANA for c in a)
    if pb.pos1 == '名詞' and KATAKANA_PAIR_REGEX.fullmatch(a):
      return True
  # 悪くない warukunai; ない ない stays apart, the second is its own word
  if b == 'ない' and pa.pos1 == '形容詞' and pa.pos2 != '非自立可能':
    return True
  # a filler sound is part of the word it trails (と え -> toe). One kana only:
  # あの is a filler word of its own and keeps its space.
  if pb.pos2 == 'フィラー' and len(b) == 1:
    return True
  # a vowel cried on its own lengthens the word before it (ねえ -> nee); only as an
  # interjection, since a verb keeps its space (に いて stays ni ite)
  if (pb.pos1 == '感動詞' and len(b) == 1 and b in VOWEL_KANA
      and prev_roma.lower().endswith(roma.lower())):
    return True
  return None


def _respace(words, tokens):
  """Rewrite cutlet's spacing where human romaji disagrees."""
  for i in range(1, len(words)):
    prev, tok = tokens[i - 1], tokens[i]
    # keep punctuation spacing, and a space the lyric itself wrote
    if not prev.surface or not tok.surface or words[i].white_space:
      continue
    glue = _attach(words[i - 1], words[i], prev.surface, tok.surface)
    if glue is not None:
      prev.space = not glue


def _fix_tokens(words, tokens):
  """Post-passes over cutlet's tokens: gemination, then spacing."""
  _geminate_ichi(words, tokens)
  _respace(words, tokens)


# --- romanizer ---

class LyricalCutlet(cutlet.Cutlet):
  """Hepburn cutlet that reads furigana, small-kana long vowels, and n-best parses."""

  def get_single_mapping(self, pk, kk, nk):
    # A small kana repeating the vowel before it is a long vowel (ねぇ -> nee).
    # cutlet folds every small kana into the kana before it, which is right only
    # across vowels (ふぇ -> fe).
    if kk in SMALL_VOWELS and self.table.get(pk or '', '')[-1:] == self.table[kk]:
      return self.table[kk]
    if nk and nk in SMALL_VOWELS and self.table.get(kk, '')[-1:] == self.table[nk]:
      return self.table[kk]
    return super().get_single_mapping(pk, kk, nk)

  def romaji_word(self, word):
    # Furigana beats both the dictionary and EXCEPTIONS (永遠(とわ) -> towa).
    ruby = getattr(word, 'ruby', None)
    if ruby:
      return self.map_kana(jaconv.kata2hira(ruby))
    if getattr(word, 'pos_exc', None):
      return word.pos_exc
    return super().romaji_word(word)

  def _tag(self, text, spans):
    """Split into words, picking the best-scoring parse.

    Returns (words, indexes of the furigana spans used).
    """
    used = set()
    words = None
    if KANJI_REGEX.search(text) or 'ん' in text:
      paths = self.tagger.nbestToNodeList(text, NBEST)
      # Words are copied out and spacing rebuilt here: candidate words carry no
      # spacing info (ascii words would run together) and the next tagger call
      # frees them.
      best, low = 0, _path_penalty(paths[0])
      # a penalty is never negative, so a clean first parse already wins and the
      # rest need no scoring; on a tie MeCab's own order (index 0) keeps it
      if low:
        for i in range(1, len(paths)):
          score = _path_penalty(paths[i])
          if score < low:
            best, low = i, score
      if best != 0:
        words = _wrap_nodes(paths[best], text, spans, used)
    if words is None:
      words = _wrap_nodes(self.tagger(text), text, spans, used)
    return words, used

  def romaji(self, text, capitalize=True, title=False):
    if not text:
      return ""
    text = cutlet.normalize_text(text)
    if KANJI_REGEX.search(text):
      text = _zh_to_shinjitai(text)
    text = DIGIT_RUN_REGEX.sub(_kanji_number, text)
    for pat, kana in _PRE_SUB_RULES:
      text = pat.sub(kana, text)
    # last, so furigana positions match the text MeCab actually sees
    text, spans = _strip_ruby(text)
    words, used = self._tag(text, spans)
    missed = set(range(len(spans))) - used
    if missed:
      # furigana split across two words (道導 -> 道 + 導): write the kana into the
      # text instead. Reading stays right, word split gets worse.
      text, spans = _sub_spans(text, spans, missed)
      words, used = self._tag(text, spans)
    tokens = self.romaji_tokens(words, capitalize, title)
    _fix_tokens(words, tokens)
    return "".join(str(tok) for tok in tokens).strip()


# --- public API ---

@lru_cache(maxsize=None)
def _romanizer():
  # Lyric romaji spells katakana out (merodi, haato); cutlet's foreign spelling
  # would print the source word (melody, heart).
  katsu = LyricalCutlet('hepburn', use_foreign_spelling=False)
  katsu.use_tch = False  # lyric romaji writes kocchi, not cutlet's traditional kotchi
  # cutlet ships English spellings for a few words (東京 Tokyo, 弁当 bento); lyrics
  # want the reading (toukyou), same as with foreign spelling above
  katsu.exceptions = dict(EXCEPTIONS)
  return katsu


def has_japanese(text):
  """True if the text has hiragana, katakana, or Chinese characters."""
  return bool(JP_REGEX.search(text))


@lru_cache(maxsize=8192)  # a subtitle or lyric file repeats lines; keep them all
def romanize(text, capitalize=True, title=False):
  """Japanese text to Hepburn romaji. Other text passes through unchanged."""
  if not has_japanese(text):
    return text
  out = _romanizer().romaji(text, capitalize=capitalize, title=title)
  return FLOATING_N_REGEX.sub('n', out)
