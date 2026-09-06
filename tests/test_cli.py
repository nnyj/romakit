"""python -m romakit end to end."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def run(*args, stdin=None):
  return subprocess.run([sys.executable, '-m', 'romakit', *args], input=stdin,
                        capture_output=True, text=True, encoding='utf-8',
                        cwd=ROOT, check=True).stdout

def test_stdin_to_stdout():
  assert run(stdin='シナリオ\n').splitlines() == ['Scenario']

def test_no_foreign_spells_the_loanword_out():
  assert run('--no-foreign', stdin='シナリオ\n').splitlines() == ['Shinario']

def test_file_in_file_out(tmp_path):
  src = tmp_path / 'in.txt'
  src.write_text('こんにちは\n', encoding='utf-8')
  out = tmp_path / 'out.txt'
  run(str(src), '-o', str(out))
  assert out.read_text(encoding='utf-8').splitlines() == ['Konnichiha']
