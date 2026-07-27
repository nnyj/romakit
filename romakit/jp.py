"""Japanese to romaji using cutlet, tuned for song lyrics.

Adds on top of plain cutlet:
- EXCEPTIONS: extra word -> reading pairs, merged into cutlet's table at startup
- long vowels collapsed from UniDic pron (toukyou -> tokyo)
- lone romanized n glued back to the word before it (mie n -> mien)
- furigana used as the reading
- kun'yomi over on'yomi where MeCab misleans

On that last point: MeCab is trained on normal text, so a kanji standing alone
usually gets on'yomi (jutsu, kuu, jin) while lyrics want kun'yomi (sube, sora,
hito). _path_penalty scores MeCab's n-best parses, pushing down those on'yomi
picks and junk parses.

Unsolved: two kun'yomi candidates (soba vs gawa) give no signal, so those words
go in EXCEPTIONS; ateji needs furigana or the audio.

Terms are used bare here; see README Glossary.
"""
import warnings
from functools import lru_cache

import cutlet
import jaconv
import regex as re

# --- word overrides ---

# Fixed reading, applied only when MeCab splits the word off as a whole token, so
# compounds like 内側/台風/私立 are untouched. Covers what the re-ranker cannot see
# (both readings native) and words unidic gets wrong (刹那 -> "Ksana").
EXCEPTIONS = {
  '私': 'watashi',
  '風': 'kaze',
  '側': 'soba',
  '刹那': 'setsuna',
  '擦り': 'kosuri',
  # asu and ashita are about equally common; songs meaning asu usually print
  # furigana, so ashita is the safer default
  '明日': 'ashita',
  '本当': 'hontou',   # unidic pron honto
  '身体': 'karada',   # unidic picks shintai
  '言う': 'iu',       # unidic picks yuu
  '今日': 'kyou',
  '嗚呼': 'aa',
  '瞬く': 'matataku',  # unidic sometimes shibatataku
  '開け': 'ake',
  '硝子': 'garasu',    # whole-word reading, unidic reads per kanji: shoushi
  '怒り': 'ikari',
  '弱音': 'yowane',    # unidic jakuon
  '上手': 'jouzu',
  '塗れ': 'mamire',
  '一途': 'ichizu',
  '甘え': 'amae',
  # lyrics printing furigana for these always show the same reading
  '永久': 'towa',        # unidic eikyuu
  '幼': 'osana',         # as a noun unidic says you; 幼い/幼子 are own tokens
  '水面': 'minamo',      # unidic suimen
  '明後日': 'asatte',    # unidic myougonichi
  '泡沫': 'utakata',     # unidic houmatsu
  '宴': 'utage',         # unidic en
  '数多': 'amata',       # unidic suuta
  '昂': 'taka',          # unidic name reading Noboru
  '鋼': 'hagane',        # unidic suffix kou
  '灯火': 'tomoshibi',   # unidic touka
  '躯': 'karada',        # unidic mukuro (lemma 骸)
  '貴女': 'anata',       # unidic kijo
  '弛': 'tayu',          # alone only; 弛む stays tarumu (both real words)
  '道標': 'michishirube',  # unidic douhyou
  '群': 'mure',          # alone only; 群衆/群青 are own tokens
  '埋もれ': 'umore',     # in a sentence unidic picks the bookish uzumore
  '海月': 'kurage',      # unidic kaigetsu
  # furigana nearly always prints ひと; compounds are own tokens (他人事 hitogoto).
  # Known miss: 他人行儀 splits into 他人+行儀 -> "hito gyougi"; every kana spelling
  # of taningyougi splits worse.
  '他人': 'hito',
  'ガラス': 'garasu',    # foreign spelling gives the Dutch source word "Glas"
  'ソーブツ': 'soubutsu',  # pairs with the 創物 entry in PRE_SUB
  # unidic picks a rare on'yomi for all of these
  '闇夜': 'yamiyo',      # unidic an'ya, the reading of 暗夜
  '傷痕': 'kizuato',     # unidic shoukon
  '上辺': 'uwabe',       # unidic jouhen, not a real reading
  '泥水': 'doromizu',    # unidic deisui
  '嚆矢': 'koushi',      # unidic outputs the name Hajime
}
# Same idea, but bare word only: any word before it turns the override off.
# 性 alone is saga, as an ending (可能性) sei. 的 alone is the noun mato
# (的外れ matohazure), as an ending (大人的) teki.
POS_EXCEPTIONS = {('性', '名詞'): 'saga', ('的', '接尾辞'): 'mato'}
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
KATAKANA_REGEX = re.compile(r'[\p{IsKatakana}]')
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

# Words unidic gets wrong and splits into several tokens. EXCEPTIONS is one token
# only, so it cannot reach these (勿れ splits into 勿+れ). 言叶 belongs here because
# 叶 is in JP_SAFE, so opencc never touches that group.
PRE_SUB = {
  '勿れ': 'なかれ',
  '兎に角': 'とにかく',
  '兎にも角にも': 'とにもかくにも',
  '言叶': '言葉',
  # opencc turns 关 into 関 but leaves 系 (JP_SAFE), so 关系 stops at 関系 and never
  # reaches 関係. Finish it here.
  '関系': '関係',
  # More half-fixed cases: 后/云/壁 are JP_SAFE, so opencc skips the group (最后,
  # 明后日, 羊云) or fixes only the other character (准备 -> 准備, 云间 -> 云間).
  # 复 converts, but to 復, the wrong twin of 複.
  # Keys below are the shape the text has after the opencc step.
  '最后': '最後',
  '准備': '準備',
  '明后日': '明後日',   # EXCEPTIONS then gives asatte
  '云間': '雲間',
  '羊云': '羊雲',
  '復雑': '複雑',
  '完壁': '完璧',       # common typo: 壁 for 璧
  # unidic splits these, so EXCEPTIONS cannot reach them. Replacements use
  # katakana: hiragana gets split again (ねんがっぴ -> "nen gap pi"), katakana
  # stays one unknown word.
  '幻花': 'ゲンカ',        # split 幻+花 -> maboroshi hana
  '紅塵': 'コウジン',      # split 紅+塵 -> kurenai gomi
  '咽返る': 'ムセカエル',  # split 咽+返る -> nodo kaeru; must precede 咽返
  '咽返': 'ムセカエ',
  '風見鶏': 'カザミドリ',  # split 風見+鶏 -> kazami niwatori
  '極彩色': 'ゴクサイシキ',  # split 極+彩色 -> kyoku saishiki
  '覚束ぬ': 'オボツカヌ',  # 覚束 splits into 覚+束 kakuzoku; 覚束ない/覚束無い fine
  '創物': 'ソーブツ',      # missing from unidic; ソウブツ splits, ソー stays one word
  # unidic splits these and gets the first half wrong; katakana forms come out
  # right (a few still split, which only affects spacing)
  '不器用': 'ブキヨウ',    # split 不+器用 -> fu kiyou
  '何気': 'ナニゲ',        # split 何+気 -> nan ge / nani ki; always nanige (何気ない)
  '何遍': '何ベン',        # 遍 becomes pen here; 何 stays a number so nan+ben joins
  '赤信号': 'アカシンゴウ',  # unidic reads 赤 as セキ, no other parse fixes it
  '心配性': 'しんぱいしょう',  # splits 心配+性, and 性 after a noun is sei by design
  '洗濯物': '洗濯モノ',    # split 洗濯+物 -> sentaku butsu
  '三日月': 'ミカヅキ',    # split 三+日+月 -> mikka tsuki
  # Left broken: 空回って/空回る come out "sora mawatte" (空回り is fine). Every kana
  # spelling of karamawa splits into カラ+マワ, reading worse than the original.
}
# A key ending in kanji may carry its own furigana (幻花(げんか)). Replacing the
# kanji there breaks FURIGANA_REGEX and leaves the brackets in the output, so skip
# the replacement and let the furigana win.
_RUBY_AHEAD = r'(?![(（][\p{IsHira}\p{IsKatakana}ー]+[)）])'
_PRE_SUB_RULES = [(re.compile(src + (_RUBY_AHEAD if kanji_char(src[-1]) else '')), dst)
                  for src, dst in PRE_SUB.items()]


# --- furigana handling ---

class _Node:
  """Copy of a fugashi word, with leading spacing taken from the source text."""
  __slots__ = ('surface', 'feature', 'is_unk', 'char_type', 'white_space', 'collapse_ok',
               'ruby', 'pos_exc')


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


HONORIFICS = ('様', 'さま', 'さん', 'ちゃん', 'くん', '君')


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
    n.collapse_ok = False
    nodes.append(n)
    if idx >= 0:
      pos = idx + len(w.surface)
  # Shorten long vowels in place names only, and not when the name addresses a
  # person: unidic reads 王子様 as place name + 様, but it means prince.
  for i, n in enumerate(nodes):
    nxt = nodes[i + 1] if i + 1 < len(nodes) else None
    prev = nodes[i - 1] if i > 0 else None
    n.collapse_ok = (n.feature.pos3 == '地名'
                     and not (nxt is not None and nxt.surface in HONORIFICS))
    n.pos_exc = (None if prev is not None and prev.feature.pos1 in NO_EXC_AFTER
                 else POS_EXCEPTIONS.get((n.surface, n.feature.pos1)))
    # In the set phrase 夜が明ける, 夜 reads yo; alone it stays yoru (夜に駆ける).
    # Handled here, not by _path_penalty: the yo parse drops out of the top 4 on
    # longer lines.
    nxt2 = nodes[i + 2] if i + 2 < len(nodes) else None
    if (n.surface == '夜' and nxt is not None and nxt.surface in ('が', 'は')
        and nxt2 is not None and nxt2.surface.startswith('明')):
      n.pos_exc = 'yo'
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
    if (HAN_RUN_REGEX.fullmatch(w.surface) and w.surface not in EXCEPTIONS
        and cutlet.has_foreign_lemma(w)):
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


# --- romanizer ---

class LyricalCutlet(cutlet.Cutlet):
  """Hepburn cutlet that also shortens long vowels from the UniDic pron field."""

  def romaji_word(self, word):
    # Furigana beats both the dictionary and EXCEPTIONS (永遠(とわ) -> towa).
    # Katakana furigana goes back through MeCab so foreign words keep their
    # original spelling (君(ハート) -> heart, not haato).
    ruby = getattr(word, 'ruby', None)
    if ruby:
      if KATAKANA_REGEX.search(ruby):
        return self.romaji(ruby, capitalize=False)
      return self.map_kana(ruby)
    if getattr(word, 'pos_exc', None):
      return word.pos_exc
    # Shorten long vowels in place names only (toukyou -> tokyo), matching fan
    # romaji: normal words keep the doubled vowel (kuuki, zutto), person names stay
    # ryousuke, borrowed words like juudou -> judo live in EXCEPTIONS.
    # collapse_ok comes from _wrap_nodes, which can see the nearby words.
    if (getattr(word, 'collapse_ok', False)
        and word.surface not in self.exceptions
        and word.feature.pron and 'ー' in word.feature.pron
        and not (self.use_foreign_spelling and cutlet.has_foreign_lemma(word))):
      return self.map_kana(jaconv.kata2hira(word.feature.pron.replace('ー', '')))
    return super().romaji_word(word)

  def _tag(self, text, spans):
    """Split into words, picking the best-scoring parse.

    Returns (words, indexes of the furigana spans used).
    """
    used = set()
    words = None
    if KANJI_REGEX.search(text) or 'ん' in text:
      paths = self.tagger.nbestToNodeList(text, NBEST)
      # On a tie min keeps MeCab's own order (index 0 is its first choice).
      # Words are copied out and spacing rebuilt here: candidate words carry no
      # spacing info (ascii words would run together) and the next tagger call
      # frees them.
      best = min(range(len(paths)), key=lambda i: _path_penalty(paths[i]))
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
    _geminate_ichi(words, tokens)
    return "".join(str(tok) for tok in tokens).strip()


# --- public API ---

@lru_cache(maxsize=None)
def _romanizer():
  katsu = LyricalCutlet('hepburn')
  katsu.use_foreign_spelling = True
  katsu.exceptions.update(EXCEPTIONS)
  return katsu


def has_japanese(text):
  """True if the text has hiragana, katakana, or Chinese characters."""
  return bool(JP_REGEX.search(text))


@lru_cache(maxsize=512)
def romanize(text, capitalize=True, title=False):
  """Japanese text to Hepburn romaji. Other text passes through unchanged."""
  if not has_japanese(text):
    return text
  out = _romanizer().romaji(text, capitalize=capitalize, title=title)
  return FLOATING_N_REGEX.sub('n', out)
