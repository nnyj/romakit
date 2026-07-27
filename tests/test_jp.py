from romakit.jp import romanize


class TestFurigana:
  """Kana in brackets after kanji is the reading: use it, drop brackets."""

  def test_ruby_reading_beats_dictionary_and_exceptions(self):
    assert romanize('永遠(とわ)になりたい') == 'Towa ni naritai'
    assert romanize('明日(あす)') == 'Asu'              # EXCEPTIONS says ashita
    assert romanize('君(ハート)') == 'Heart'            # katakana keeps foreign spelling

  def test_kanji_surface_kept_for_segmentation(self):
    # MeCab needs the kanji to split words; all-kana splits wrong (澄んだ -> すんだ)
    assert romanize('澄(す)んだ色(いろ)に染(そ)まる') == 'Sunda iro ni somaru'
    assert romanize('外(はず)して微笑(ほほえ)んだあなた') == 'Hazushite hohoenda anata'

  def test_ruby_spans_whole_kanji_run(self):
    assert romanize('大好(だいす)きだよ') == 'Daisuki da yo'

  def test_straddling_ruby_falls_back_to_kana(self):
    # reading covers 道 + 導, two words: no word can take it, so kana is used
    assert romanize('道導(みちしるべ)') == 'Michishirube'

  def test_pre_sub_yields_to_ruby(self):
    # a PRE_SUB replacement here would leave brackets in the output
    assert romanize('幻花(げんか)') == 'Genka'

  def test_non_kana_parens_untouched(self):
    assert romanize('(2番)ここから') == '(2 ban) koko kara'

  def test_numeral_counter_ruby(self):
    # unidic keeps 1人 as one word, so the reading came out "1ひとり" and cutlet's
    # kana table raised KeyError('1'); kana already says the number
    assert romanize('1人(ひとり)過ごした孤独な時') == 'Hitori sugoshita kodoku na toki'
    assert romanize('２人(ふたり)だけ') == 'Futari dake'
    assert romanize('何もない1日(いちにち)なんてない') == 'Nani mo nai ichinichi nante nai'


class TestZhRepair:
  """opencc fixes Chinese character shapes without touching valid Japanese."""

  def test_zh_glyphs_converted(self):
    assert romanize('乐谱も书けないし') == 'Gakufu mo kakenaishi'
    assert romanize('隐れて消えたい') == 'Kakurete kietai'
    assert romanize('青空、流线を そっと导いて') == 'Aozora, ryuusen wo sotto michibiite'

  def test_jp_safe_glyphs_survive(self):
    # each a real Japanese kanji opencc would change (机->機, 叶->葉, 里->裏)
    assert romanize('机の上に置いた') == 'Tsukue no ue ni oita'
    assert romanize('夢を叶える') == 'Yume wo kanaeru'
    assert romanize('里の風') == 'Sato no kaze'
    assert romanize('蝉の声') == 'Semi no koe'

  def test_all_japanese_runs_skip_conversion(self):
    # opencc would give 迴路 / 灑落 if these groups converted
    assert romanize('思考回路') == 'Shikou kairo'
    assert romanize('少し洒落た店') == 'Sukoshi shareta mise'

  def test_corrupt_run_keeps_correct_glyphs(self):
    # 负 needs fixing, 背 does not; converting the whole group gives 揹負
    assert romanize('伤を背负った') == 'Kizu wo seotta'

  def test_word_context_disambiguates(self):
    # same 发, two readings; a per-character table cannot do this
    assert romanize('发型を変える') == 'Kamigata wo kaeru'
    assert romanize('头发を切った') == 'Touhatsu wo kitta'

  def test_half_repaired_zh_word_finished_by_pre_sub(self):
    # 关系 -> 関系 (系 is JP_SAFE so opencc stops there) -> 関係
    assert romanize('ぜんぜん关系ない') == 'Zenzen kankei nai'
    # same idea: opencc skips the group (后/云 are JP_SAFE) or fixes only half
    assert romanize('最后にもう一度') == 'Saigo ni mou ichi do'
    assert romanize('明后日に考えよう') == 'Asatte ni kangaeyou'
    assert romanize('准备したのさ') == 'Junbi shita no sa'
    assert romanize('云间に 刻み込んだ') == 'Kumoma ni kizamikonda'
    assert romanize('复雑') == 'Fukuzatsu'
    assert romanize('完壁とは言えなくても') == 'Kanpeki to wa ienakute mo'   # 壁 typo for 璧

  def test_no_opencc_falls_back_to_passthrough(self, monkeypatch):
    from romakit import jp
    monkeypatch.setattr(jp, '_s2t', None)
    jp.romanize.cache_clear()
    assert jp._zh_to_shinjitai('乐谱') == '乐谱'
    assert romanize('机の上に置いた') == 'Tsukue no ue ni oita'
    jp.romanize.cache_clear()


class TestReadings:
  """Reading choice, word overrides, doubled consonants, long vowels."""

  def test_kun_preferred(self):
    assert romanize('空を見上げて') == 'Sora wo miagete'
    assert romanize('術がない') == 'Sube ga nai'

  def test_token_exceptions(self):
    assert romanize('私の風') == 'Watashi no kaze'
    assert romanize('本当に今日は') == 'Hontou ni kyou wa'
    assert romanize('身体') == 'Karada'
    assert romanize('永久の美しさよ') == 'Towa no utsukushisa yo'
    assert romanize('水面に広がる') == 'Minamo ni hirogaru'
    assert romanize('黙っている貴女と') == 'Damatte iru anata to'

  def test_osana_keeps_okurigana_forms(self):
    assert romanize('思い出す幼き日') == 'Omoidasu osana ki nichi'
    assert romanize('幼い頃') == 'Osanai koro'
    assert romanize('幼子') == 'Osanago'

  def test_saga_only_as_bare_noun(self):
    assert romanize('逸脱の性を') == 'Itsudatsu no saga wo'
    assert romanize('可能性') == 'Kanou sei'   # 〜性 suffix stays sei
    assert romanize('危険性') == 'Kikensei'

  def test_mure_and_umore(self):
    assert romanize('思い上がる群は歪みに埋もれた') == 'Omoiagaru mure wa yugami ni umoreta'
    assert romanize('群衆') == 'Gunshuu'   # compounds keep on'yomi

  def test_mato_only_as_stemless_suffix(self):
    assert romanize('的外れても叫びを止めれない') == 'Mato hazurete mo sakebi wo tomerenai'
    assert romanize('俺的には') == 'Oreteki ni wa'   # 〜的 after a word stays teki
    assert romanize('大人的な考え') == 'Otonateki na kangae'
    assert romanize('目的') == 'Mokuteki'

  def test_split_compounds_via_pre_sub(self):
    assert romanize('誰が袖に咲く幻花') == 'Dare ga sode ni saku genka'
    assert romanize('咽返る魅惑') == 'Musekaeru miwaku'
    assert romanize('風見鶏 飛べずに') == 'Kazamidori tobezu ni'

  def test_kanji_foreign_lemma_rejected(self):
    # unidic reads 汗 as ハン (Khan); Japanese reading must win
    assert romanize('グラウンド 汗光らせ') == 'Ground ase hikarase'

  def test_exceptions_exempt_from_foreign_lemma_penalty(self):
    # 刹那's entry is the Sanskrit "ksana", so the foreign-name rule pushed down
    # the one-word parse and split it into 刹 + 那 ("Setsu ano")
    assert romanize('刹那') == 'Setsuna'
    assert romanize('刹那を繰り返す') == 'Setsuna wo kurikaesu'

  def test_jukujikun_and_lexicon_gaps(self):
    assert romanize('海月のような月が爆ぜた') == 'Kurage no you na tsuki ga hazeta'
    assert romanize('ガラス') == 'Garasu'            # foreign spelling gave Dutch "Glas"
    assert romanize('硝子(ガラス)の心') == 'Garasu no kokoro'
    assert romanize('凍てつく 闇夜も恐れない') == 'Itetsuku yamiyo mo osorenai'
    assert romanize('泥水で顔を洗って') == 'Doromizu de kao wo aratte'
    assert romanize('進撃の嚆矢は') == 'Shingeki no koushi wa'

  def test_hito_only_as_bare_token(self):
    assert (romanize('他人に優しいあんたにこの孤独がわかるものか')
            == 'Hito ni yasashii anta ni kono kodoku ga wakaru mono ka')
    assert romanize('他人事') == 'Hitogoto'   # own word, the override cannot reach it

  def test_yo_ga_akeru_idiom(self):
    assert romanize('夜が明けて') == 'Yo ga akete'
    assert romanize('覚束ぬままに夜が明けて') == 'Obotsukanu mama ni yo ga akete'
    assert romanize('夜が明けるまで語り続けてた') == 'Yo ga akeru made katari tsuzuketeta'
    assert romanize('夜に駆ける') == 'Yoru ni kakeru'   # plain 夜 stays yoru

  def test_odokasu_vs_obiyakasu(self):
    assert romanize('脅かして') == 'Odokashite'
    assert romanize('命を脅かした') == 'Inochi wo obiyakashita'   # を marks the object

  def test_mekuramashi_vs_memai(self):
    assert romanize('目眩して') == 'Mekuramashite'
    assert romanize('目眩がする') == 'Memai ga suru'   # bare noun stays memai

  def test_okurigana_forms_unaffected_by_pre_sub(self):
    assert romanize('覚束ない') == 'Obotsukanai'
    assert romanize('空回り') == 'Karamawari'
    assert romanize('空回転') == 'Sora kaiten'

  def test_split_compound_readings(self):
    assert romanize('無自覚の創物って') == 'Mujikaku no soubutsu tte'
    assert romanize('不器用だから全てが') == 'Bukiyou dakara subete ga'
    assert romanize('何気ない日でも') == 'Nanige nai hi de mo'
    assert romanize('言葉が何遍も') == 'Kotoba ga nanben mo'
    assert romanize('赤信号でも直進でしょ') == 'Akashingou de mo chokushin desho'
    assert romanize('空に浮かぶ三日月') == 'Sora ni ukabu mikazuki'
    assert romanize('理不尽な我慢') == 'Ri fujin na gaman'

  def test_ateji_defaults_kept(self):
    # songs sometimes give these a poetic reading; only furigana can change them
    assert romanize('運命') == 'Unmei'
    assert romanize('未来') == 'Mirai'
    assert romanize('有耶無耶になる') == 'Uyamuya ni naru'

  def test_numeral_gemination(self):
    assert romanize('震える一歩') == 'Furueru ippo'
    assert romanize('もう一回') == 'Mou ikkai'
    assert romanize('一日中') == 'Ichi nichijuu'  # starts with n, no doubling
    assert romanize('一つ') == 'Hitotsu'          # this counter reads 一 as hito

  def test_place_name_long_vowel_collapse(self):
    assert romanize('東京へ行く') == 'Tokyo e iku'

  def test_foreign_spelling(self):
    assert romanize('あぁ 美味しいカレーが 食べたいな') == 'A oishii curry ga tabetai na'

  def test_floating_n_reattach(self):
    assert romanize('分からんよ') == 'Wakaran yo'

  def test_non_japanese_passthrough(self):
    assert romanize('hello world') == 'hello world'
