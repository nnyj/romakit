"""CLI: romakit [input] [-o out] [--lang jp|cn|kr]

Line by line, stdin to stdout unless paths are given.
Japanese needs the unidic dictionary: python -m unidic download
"""
import argparse
import sys
from pathlib import Path

from . import LANGS, romanize

def main():
  parser = argparse.ArgumentParser(prog='romakit')
  parser.add_argument('input', nargs='?', help='input file, default stdin')
  parser.add_argument('-o', '--output', help='output file, default stdout')
  parser.add_argument('--lang', choices=LANGS, default='auto',
                      help='lyric language; auto guesses per line (default)')
  args = parser.parse_args()

  sys.stdin.reconfigure(encoding='utf-8')
  sys.stdout.reconfigure(encoding='utf-8')
  text = Path(args.input).read_text(encoding='utf-8') if args.input else sys.stdin.read()
  out = ''.join(romanize(line, args.lang) + '\n' for line in text.splitlines())
  if args.output:
    Path(args.output).write_text(out, encoding='utf-8')
  else:
    print(out, end='')

if __name__ == '__main__':
  main()
