import subprocess
import sys

from romakit.jp import romanize

class TestFurigana:
  """Kana in brackets after kanji is the reading: use it, drop brackets."""

  def test_ruby_reading_beats_dictionary_and_exceptions(self):
    assert romanize('永遠(とわ)になりたい') == 'Towa ni naritai'
    assert romanize('明日(あす)') == 'Asu'              # the reading table says ashita
    assert romanize('君(ハート)') == 'Haato'            # katakana ruby is spelled out

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
    assert romanize('三日月(みかづき)') == 'Mikazuki'

  def test_non_kana_parens_untouched(self):
    assert romanize('(2番)ここから') == '(niban) koko kara'

  def test_numeral_counter_ruby(self):
    # unidic keeps 1人 as one word, so the reading comes out "1ひとり" and cutlet's
    # kana table raises KeyError('1'); kana already says the number
    assert romanize('1人(ひとり)過ごした孤独な時') == 'Hitori sugoshita kodoku na toki'
    assert romanize('２人(ふたり)だけ') == 'Futari dake'
    assert romanize('何もない1日(いちにち)なんてない') == 'Nani mo nai ichinichi nante nai'

class TestZhRepair:
  """opencc fixes Chinese character shapes without touching valid Japanese."""

  def test_zh_glyphs_converted(self):
    assert romanize('乐谱も书けないし') == 'Gakufu mo kakenai shi'
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
    assert romanize('最后にもう一度') == 'Saigo ni mou ichido'
    assert romanize('明后日に考えよう') == 'Asatte ni kangaeyou'
    assert romanize('准备したのさ') == 'Junbi shita no sa'
    assert romanize('云间に 刻み込んだ') == 'Kumoma ni kizamikonda'
    assert romanize('复雑') == 'Fukuzatsu'
    assert romanize('完壁とは言えなくても') == 'Kanpeki to wa ienakute mo'   # 壁 typo for 璧

  def test_no_opencc_falls_back_to_passthrough(self):
    # a fresh interpreter with the import blocked, so the test knows nothing about
    # how the fallback is wired
    code = ('import sys, warnings; sys.modules["opencc"] = None;'
            'warnings.simplefilter("ignore");'
            'from romakit.jp import romanize;'
            'print(romanize("机の上に置いた"))')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, encoding='utf-8')
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == 'Tsukue no ue ni oita'

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
    assert romanize('思い出す幼き日') == 'Omoidasu osanaki hi'
    assert romanize('幼い頃') == 'Osanai koro'
    assert romanize('幼子') == 'Osanago'

  def test_saga_only_as_bare_noun(self):
    assert romanize('逸脱の性を') == 'Itsudatsu no saga wo'
    assert romanize('可能性') == 'Kanousei'   # 〜性 suffix stays sei
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
    assert romanize('咽返る魅惑') == 'Musekaeru miwaku'
    assert romanize('風見鶏 飛べずに') == 'Kazamidori tobezu ni'

  def test_kanji_foreign_lemma_rejected(self):
    # unidic reads 汗 as ハン (Khan); Japanese reading must win
    assert romanize('グラウンド 汗光らせ') == 'Guraundo ase hikarase'

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
    assert romanize('良い日') == 'Ii hi'
    assert romanize('灰になる') == 'Hai ni naru'
    assert romanize('頬を伝う') == 'Hoho wo tsutau'
    assert romanize('刃を向ける') == 'Yaiba wo mukeru'
    assert romanize('君と僕') == 'Kimi to boku'   # unidic reads the name suffix kun

  def test_cutlet_english_spellings_dropped(self):
    # cutlet ships English spellings for these; lyric romaji wants the reading
    assert romanize('東京の夜') == 'Toukyou no yoru'
    assert romanize('弁当') == 'Bentou'

  def test_tabi_and_sei_only_as_bare_nouns(self):
    assert romanize('この度は') == 'Kono tabi wa'
    assert romanize('一度だけ') == 'Ichido dake'   # after a number, the counter
    assert romanize('生を受けて') == 'Sei wo ukete'
    assert romanize('生きる') == 'Ikiru'           # verb, untouched

  def test_pruned_readings_fall_back_to_mecab(self):
    # both readings are real and human romaji prefers unidic's, so no override
    # 他人 is sung hito here, but tanin is the wider-corpus reading and both are
    # real, so nothing ranks them; only furigana can pick hito
    assert (romanize('他人に優しいあんたにこの孤独がわかるものか')
            == 'Tanin ni yasashii anta ni kono kodoku ga wakaru mono ka')
    assert romanize('他人事') == 'Hitogoto'   # own word, unaffected
    assert romanize('躯') == 'Mukuro'
    assert romanize('夜が明けて') == 'Yo ga akete'   # the idiom reads yo
    assert romanize('夜に駆ける') == 'Yoru ni kakeru'

  def test_lexicon_gap_readings(self):
    assert romanize('川の流れ') == 'Kawa no nagare'
    assert romanize('小川') == 'Ogawa'          # own word, keeps the suffix reading
    assert romanize('悪の華') == 'Aku no hana'
    assert romanize('塵になる') == 'Chiri ni naru'
    assert romanize('一日') == 'Ichinichi'
    assert romanize('一日中') == 'Ichinichijuu'
    assert romanize('春風が') == 'Harukaze ga'
    assert romanize('僕等の歌') == 'Bokura no uta'
    assert romanize('跡形も無き') == 'Atokata mo naki'

  def test_digits_read_as_kanji_numerals(self):
    # rewritten before tagging, so unidic supplies the counter phonology
    assert romanize('1つの夢') == 'Hitotsu no yume'
    assert romanize('3時に') == 'Sanji ni'
    assert romanize('1分') == 'Ippun'
    assert romanize('12時') == 'Juuniji'
    assert romanize('100年') == 'Hyakunen'
    assert romanize('0を数えて') == 'Zero wo kazoete'   # a bare 0 is zero, not rei

  def test_odokasu_vs_obiyakasu(self):
    assert romanize('脅かして') == 'Odokashite'
    assert romanize('命を脅かした') == 'Inochi wo obiyakashita'   # を marks the object

  def test_mekuramashi_vs_memai(self):
    assert romanize('目眩して') == 'Mekuramashite'
    assert romanize('目眩がする') == 'Memai ga suru'   # bare noun stays memai

  def test_okurigana_forms_unaffected_by_pre_sub(self):
    assert romanize('覚束ない') == 'Obotsukanai'
    assert romanize('空回り') == 'Karamawari'
    assert romanize('空回転') == 'Karakaiten'

  def test_split_compound_readings(self):
    assert romanize('無自覚の創物って') == 'Mujikaku no soubutsu tte'
    assert romanize('不器用だから全てが') == 'Bukiyou dakara subete ga'
    assert romanize('何気ない日でも') == 'Nanige nai hi demo'
    assert romanize('言葉が何遍も') == 'Kotoba ga nanben mo'
    assert romanize('赤信号でも直進でしょ') == 'Akashingou demo chokushin desho'
    assert romanize('空に浮かぶ三日月') == 'Sora ni ukabu mikazuki'
    assert romanize('理不尽な我慢') == 'Rifujin na gaman'

  def test_ateji_defaults_kept(self):
    # songs sometimes give these a poetic reading; only furigana can change them
    assert romanize('運命') == 'Unmei'
    assert romanize('未来') == 'Mirai'
    assert romanize('有耶無耶になる') == 'Uyamuya ni naru'

  def test_numeral_gemination(self):
    assert romanize('震える一歩') == 'Furueru ippo'
    assert romanize('もう一回') == 'Mou ikkai'
    assert romanize('一日中') == 'Ichinichijuu'   # starts with n, no doubling
    assert romanize('一つ') == 'Hitotsu'          # this counter reads 一 as hito

  def test_katakana_spelled_out(self):
    # cutlet's foreign spelling would print the source words (curry, melody)
    assert romanize('あぁ 美味しいカレーが 食べたいな') == 'Aa oishii karee ga tabetai na'
    assert romanize('メロディーが響く') == 'Merodii ga hibiku'

  def test_floating_n_reattach(self):
    assert romanize('分からんよ') == 'Wakaran yo'

  def test_non_japanese_passthrough(self):
    assert romanize('hello world') == 'hello world'

class TestSpacing:
  """Joins and splits rewritten over cutlet's part-of-speech spacing."""

  def test_particle_clusters_join(self):
    assert romanize('でもいつか誰かに') == 'Demo itsuka dareka ni'
    assert romanize('そうなんだよ') == 'Sou nanda yo'
    assert romanize('好きなのかな') == 'Suki nano kana'
    assert romanize('雨だって降る') == 'Ame datte furu'

  def test_indefinite_ka_joins_question_words(self):
    # the join is keyed on the question word's part of speech, not a word list
    assert romanize('だれかに') == 'Dareka ni'
    assert romanize('どこかで待ってる') == 'Dokoka de matteru'
    assert romanize('いつしか消えた') == 'Itsushika kieta'
    assert romanize('そうか') == 'Sou ka'   # here か asks, it is not part of a word

  def test_quoting_tte_splits_off_the_copula(self):
    assert romanize('好きって言って') == 'Suki tte itte'
    assert romanize('いいねって') == 'Ii ne tte'
    assert romanize('なんだって言うの') == 'Nandatte iu no'   # on だ it stays solid

  def test_conjunctions_split_but_dakara_joins(self):
    assert romanize('行かないから') == 'Ikanai kara'
    assert romanize('痛いけど笑う') == 'Itai kedo warau'
    assert romanize('だから走る') == 'Dakara hashiru'
    assert romanize('進んで行く') == 'Susunde iku'   # て/で stay attached
    assert romanize('泣かなくちゃ') == 'Nakanakucha'
    assert romanize('何を言ったって') == 'Nani wo ittatte'
    assert romanize('泣いたり笑ったり') == 'Naitari warattari'

  def test_split_compound_nouns_rejoin(self):
    # unidic splits these, human romaji writes one word
    assert romanize('交差点で') == 'Kousaten de'
    assert romanize('路地裏の猫') == 'Rojiura no neko'
    assert romanize('蜃気楼') == 'Shinkirou'

  def test_conjectural_auxiliary_splits(self):
    assert romanize('会えるなら') == 'Aeru nara'
    assert romanize('嘘だろう') == 'Uso darou'

  def test_counter_and_small_tsu_join(self):
    assert romanize('もう一度だけ') == 'Mou ichido dake'
    assert romanize('何度でも') == 'Nando demo'
    assert romanize('ずっとそばに') == 'Zutto soba ni'

  def test_helper_verbs_and_suffix_particles_join(self):
    assert romanize('歩き出す') == 'Arukidasu'
    assert romanize('消えそうな声') == 'Kiesou na koe'
    assert romanize('楽しそうな顔') == 'Tanoshisou na kao'
    assert romanize('一人きりで少しずつ') == 'Hitorikiri de sukoshizutsu'
    assert romanize('悪くない') == 'Warukunai'
    assert romanize('悲しさが') == 'Kanashisa ga'

  def test_adverbial_sou_keeps_its_space(self):
    assert romanize('そうさ僕は') == 'Sou sa boku wa'
    assert romanize('そうだよ') == 'Sou da yo'

  def test_verb_keeps_its_space(self):
    # the vowel and helper rules must not swallow a real verb
    assert romanize('傍にいて') == 'Soba ni ite'
    assert romanize('僕は歌う') == 'Boku wa utau'

class TestLongVowels:
  """Small kana and repeated vowels are written out, not dropped."""

  def test_small_vowel_lengthens(self):
    assert romanize('ねぇ') == 'Nee'
    assert romanize('あぁ') == 'Aa'
    assert romanize('さぁ行こう') == 'Saa ikou'

  def test_small_vowel_across_rows_stays_a_digraph(self):
    assert romanize('フェイク') == 'Feiku'
    assert romanize('チェック') == 'Chekku'

  def test_repeated_interjection_joins(self):
    assert romanize('ねえねえ') == 'Nee nee'
    assert romanize('ああああ') == 'Aaaa'
    assert romanize('ほらほら') == 'Hora hora'   # a repeated word is still two words
    assert romanize('バイバイまたね') == 'Baibai mata ne'   # two-mora katakana doubles

  def test_filler_kana_leans_on_the_word_before(self):
    assert romanize('たとえ君が') == 'Tatoe kimi ga'
    assert romanize('あのね') == 'Ano ne'   # a filler word of its own keeps its space

  def test_cchi_over_tchi(self):
    assert romanize('こっちだよ') == 'Kocchi da yo'
    assert romanize('ひとりぼっち') == 'Hitoribocchi'

class TestLyricRules:
  """Rules from the lyric corpus; each line is a real lyric."""

  def test_contracted_n_glues_left(self):
    assert romanize('わかるんだ') == 'Wakarun da'
    assert romanize('間違ってるんだよ') == 'Machigatterun da yo'
    assert romanize('どうでもいいんだ') == 'Dou demo iin da'
    assert romanize('あのね、忘れたいんだけど') == 'Ano ne, wasuretain dakedo'
    assert romanize('靴を捨てたんだっけ') == 'Kutsu wo sutetan dakke'

  def test_contracted_n_on_the_copula_stays_one_word(self):
    assert romanize('そうなんだよ') == 'Sou nanda yo'
    assert romanize('君だけが僕の音楽なんだ') == 'Kimi dake ga boku no ongaku nanda'

  def test_katakana_separator_is_a_word_break(self):
    assert romanize('タイム・マシン') == 'Taimu mashin'
    assert romanize('ロミオ・アンド・ジュリエット') == 'Romio ando jurietto'

  def test_small_vowel_on_u_keeps_the_w(self):
    assert romanize('ウォークマン') == 'Wookuman'
    assert romanize('ウィスキー') == 'Wisukii'
    assert romanize('ウェイト') == 'Weito'

  def test_split_katakana_word_rejoins_only_when_listed(self):
    assert romanize('ラップランドの納屋の下') == 'Rappurando no naya no shita'
    assert romanize('ヒッチコックみたいな') == 'Hicchikokku mitai na'

  def test_two_word_loan_phrase_stays_split(self):
    assert romanize('ハロゲンライトだけ') == 'Harogen raito dake'
    assert romanize('魅惑ハイテンション') == 'Miwaku hai tenshon'
    assert romanize('メロンパン') == 'Meron pan'
    assert romanize('タイムマシン') == 'Taimu mashin'
    assert romanize('心も運命もラブソングも') == 'Kokoro mo unmei mo rabu songu mo'

  def test_suffix_reading_follows_the_word_before_it(self):
    assert romanize('可能性') == 'Kanousei'
    assert romanize('僕等の歌') == 'Bokura no uta'   # 等 after a pronoun reads ra
    assert romanize('一等') == 'Ittou'               # after a number it is the rank

  def test_honorific_kun_splits_off_the_noun(self):
    assert romanize('追いつけない ただ君に晴れ') == 'Oitsukenai tada kimi ni hare'

  def test_classical_ki_joins_its_stem(self):
    assert romanize('思い出す幼き日') == 'Omoidasu osanaki hi'
    assert romanize('跡形も無き') == 'Atokata mo naki'

  def test_prefix_with_nothing_to_lead_is_a_noun(self):
    assert romanize('愛') == 'Ai'          # as a prefix it would read mana
    assert romanize('愛の歌') == 'Ai no uta'

  def test_nante_reads_nan(self):
    assert romanize('何て言えばいいんだ') == 'Nante ieba iin da'
    assert romanize('何を言ったって') == 'Nani wo ittatte'

  def test_nagara_joins_its_verb(self):
    assert romanize('その時を待ちながら') == 'Sono toki wo machinagara'
    assert romanize('笑いながら顔を寄せて') == 'Warainagara kao wo yosete'

  def test_yo_ga_akeru_idiom(self):
    assert romanize('いつかやっと夜が明けたら') == 'Itsuka yatto yo ga aketara'
    assert romanize('夜に駆ける') == 'Yoru ni kakeru'

  def test_number_joins_counters_only(self):
    assert romanize('この詩はあと八十字') == 'Kono uta wa ato hachijuu ji'
    assert romanize('12時') == 'Juuniji'
    assert romanize('第六感尖らして') == 'Dairokukan togarashite'   # 第 makes one word

  def test_one_character_number_joins_the_noun_it_counts(self):
    assert romanize('そこに四次元') == 'Soko ni yojigen'
    assert romanize('指先と机の間 二次元') == 'Yubisaki to tsukue no ma nijigen'

  def test_na_adjective_stem_takes_no_suffix_join(self):
    assert romanize('綺麗事だけで') == 'Kireigoto dake de'   # 事 takes rendaku

  def test_counter_reading_needs_a_number_before_it(self):
    assert romanize('嫌　日に日に増えていた後悔を') == 'Iya hi ni hi ni fuete ita koukai wo'
    assert romanize('二日酔いが残る') == 'Futsuka yoi ga nokoru'   # 二 is the number

  def test_a_space_the_lyric_wrote_is_never_eaten(self):
    assert romanize('嫌　日に日に') == 'Iya hi ni hi ni'
    assert romanize('ただ 街を見下ろした') == 'Tada machi wo mioroshita'

  def test_soredemo_is_one_word_and_sore_de_ii_is_three(self):
    # booklet convention: それでも is the fixed conjunction, elsewhere それ is the
    # pronoun and で the copula
    assert romanize('それでも愛し愛され') == 'Soredemo aishi aisare'
    assert romanize('それでいいからもう諦めてる') == 'Sore de ii kara mou akirameteru'
    assert romanize('黙っていよう　それでいつか') == 'Damatte iyou sore de itsuka'

  def test_title_case_keeps_a_merged_counter_lowercase(self):
    assert romanize('震える一歩', title=True) == 'Furueru Ippo'

  def test_title_case_lowercases_every_merged_word(self):
    assert romanize('ロミオ・アンド・ジュリエット', title=True) == 'Romio Ando Jurietto'
    assert romanize('思い出す幼き日', title=True) == 'Omoidasu Osanaki Hi'
    assert romanize('可能性の話', title=True) == 'Kanousei no Hanashi'
