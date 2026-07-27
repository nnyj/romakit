# romakit

<div align="center">

[![Stars](https://img.shields.io/github/stars/nnyj/romakit?style=for-the-badge&labelColor=555&color=e3b341)](https://github.com/nnyj/romakit/stargazers)
[![Build](https://img.shields.io/github/actions/workflow/status/nnyj/romakit/release.yml?style=for-the-badge&labelColor=555)](https://github.com/nnyj/romakit/actions)

</div>

CJK script detection and romanization tuned for song lyrics, where general-text taggers pick the wrong reading. Detection is dependency-free; each romanizer loads lazily via its extra (`[jp]` cutlet, `[zh]` pypinyin, `[ko]` korean-romanizer).

## Features

- `detect(text)` returns `ja`, `zh`, `ko`, or empty (kana wins over han, hangul before han, bare han falls to zh)
- `is_cjk(text)` any-CJK gate, `has_japanese(text)` kana/kanji gate (unlike `detect`, true for kanji-only text)
- Japanese romaji via cutlet with lyric-oriented fixes: inline exception dict, long-vowel collapse from UniDic pron, floating contracted-n reattach, kun/on re-ranking via MeCab n-best
- Repairs zh-simplified glyph corruption in ja lyrics (`乐谱` to `楽譜`) via opencc `s2t` + `t2jp`, gated so valid JP kanji (`叶` `机` `里`) and all-Japanese runs are never rewritten
- Parenthetical furigana consumed as reading override: `外(はず)して` romanizes as `hazushite`
- `romanize(text, lang)` dispatch, `lang` one of `auto`, `jp`, `cn`, `kr`, auto uses `detect` per text
- `zh.romanize(text)` tone-less pinyin, `ko.romanize(text)` Revised Romanization

## Usage

```python
from romakit import detect, is_cjk, has_japanese, romanize

detect("夜に駆ける")      # 'ja', kana present
detect("深夜清晨")        # 'zh', han only; kanji-only ja lines also hit this, detect song-level

romanize("私は空を見た", "jp")  # 'Watashi wa sora wo mita'
romanize("你好", "cn")     # 'ni hao'
romanize("안녕하세요", "kr")  # 'annyeonghaseyo'
romanize("君の名は")        # auto: 'Kimi no na wa'
```

`romanize` is the single entry point; the per-language implementations stay reachable as `jp.romanize`, `zh.romanize`, `ko.romanize`.

Detection works without the jp extra installed; `romanize`/`has_japanese` raise ImportError on Japanese input until it is.

### CLI

Line by line, stdin to stdout unless paths are given, `--lang auto` detects per line:

```sh
romakit lyrics.txt -o romaji.txt --lang jp
cat lyrics.txt | romakit
python -m romakit lyrics.txt      # equivalent
```

## How it works

Detection is three unicode-range regexes checked in priority order, kana, hangul, han. Han-only text is ambiguous between Japanese kanji and Chinese; callers deciding per song should detect over the full lyric text (any kana anywhere means ja) rather than per line.

## Install

```sh
pip install -e .                  # detection only, zero deps
pip install -e .[jp]              # cutlet, jaconv, regex, opencc
pip install -e .[jp,zh,ko]        # add pypinyin + korean-romanizer
```

Japanese also needs the UniDic dictionary once:

```sh
python -m unidic download
```

## Glossary

Terms used bare in code comments:

| Term | Meaning |
|------|---------|
| kun'yomi | native Japanese reading of a kanji |
| on'yomi | Chinese-derived reading of a kanji |
| furigana | small kana reading printed above/beside kanji, inline as 外(はず)して |
| ateji | kanji chosen for meaning, read freely, reading not derivable |
| jukujikun | whole-word reading spanning multiple kanji (海月 kurage) |
| shinjitai | modern Japanese character forms |
| kyuujitai | pre-war Japanese character forms (樂/氣/髮) |
| gemination | consonant doubling written っ (一歩 ippo) |
| n-best | MeCab's top N parse candidates |

## Credits

- [cutlet](https://github.com/polm/cutlet): base Japanese romanization
- [pypinyin](https://github.com/mozillazg/python-pinyin): Chinese pinyin
- [korean-romanizer](https://github.com/osori/korean-romanizer): Korean Revised Romanization
- [opencc](https://github.com/BYVoid/OpenCC): zh-simplified to shinjitai glyph repair

## License

[MIT](LICENSE)
