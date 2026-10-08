# pyj — 波括弧で書く Python

[![CI](https://github.com/yyszh01/pyj/actions/workflows/ci.yml/badge.svg)](https://github.com/yyszh01/pyj/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybrace)](https://pypi.org/project/pybrace/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[English](https://github.com/yyszh01/pyj/blob/main/README.md) | [简体中文](https://github.com/yyszh01/pyj/blob/main/README.zh-CN.md) | 日本語

JavaScript のように Python を書けます。ブロックは `{ }` で囲み、文は `;` または改行で区切り、インデントには意味がありません。`.pyj` ファイルは import 時・実行時に標準の Python へ透過的に変換され、エラーは元の `.pyj` の行と列を指します。

```python
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

if n < 0 { print("negative") } else if n == 0 { print("zero") }
    else { print("positive") }
```

## 特徴

- **単一ファイル・依存関係なし**：ツール全体が標準ライブラリだけを使う 1 つの `pyj.py` で、pip や root 権限なしで自分自身をインストールできます。
- **透過的な実行**：インストール後は `python app.pyj` がそのまま動き、どのプログラムからも `.pyj` モジュールを `import` でき、`.py` と `.pyj` を自由に混在させられます。
- **シェルのワンライナーにも**：`pyj -c 'for i in range(3) { print(i) }'` のように書くことも、`pyj` にパイプでコードを渡すこともできます。
- **エラーはソースを指す**：トレースバック、構文エラー、`inspect.getsource` のすべてが `.pyj` の行と列を示します。
- **辞書や集合はいつもどおり**：ブロックの `{` とリテラルの `{` を区別します。
- **クロスプラットフォーム**：Python 3.10 以上。Linux・macOS・Windows で CI テストしています。

## インストール

### Debian・Ubuntu など pip が制限されているシステム

pip も `sudo` も特別なオプションも不要です。コマンドは 3 つだけです：

```bash
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install
rm pyj.py
```

`install` は pyj をユーザーの site-packages にコピーし、実行するすべての `python3` で `.pyj` を使えるようにして、`~/.local/bin` に `pyj` コマンドを追加します。ダウンロードしたファイルはその後不要です。シェルが `pyj` を見つけられない場合は `~/.local/bin` を `PATH` に追加してください（例：`~/.bashrc` に `export PATH="$HOME/.local/bin:$PATH"`）。`python3 app.pyj` はこの設定がなくても動きます。

アップグレードは同じ 3 つのコマンドを再実行します。削除は `pyj uninstall` です。有効化した仮想環境の中で実行すると、`install` はその仮想環境にインストールします。

### pip でインストール

```bash
pip install pybrace
```

インストール後は、その環境のすべての Python プロセスが `.pyj` を扱えるようになり、`pip uninstall pybrace` で完全に削除できます。PyPI 上のパッケージ名は `pybrace` ですが、モジュール名とコマンド名はどちらも `pyj` です。名前の似ている [mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace) とは無関係です。

システムの Python を「外部管理」としているシステム（[PEP 668](https://peps.python.org/pep-0668/)）では、`pip install` が `error: externally-managed-environment` で失敗します。上のインストーラーを使うか、次のいずれかを使ってください：

```bash
# ユーザーディレクトリへ：--user と一緒に使えば、このオプションでも書き込み先は ~/.local だけです。
# pybrace には apt のパッケージと衝突しうる依存関係がありません
pip install --user --break-system-packages pybrace

# 仮想環境（プロジェクト向けに推奨）：その venv だけが .pyj に対応します
python3 -m venv .venv && . .venv/bin/activate && pip install pybrace
```

`pipx install pybrace` も使えますが、得られるのは `pyj` コマンドだけです。この方法では、通常の `python3 app.pyj` や import は `.pyj` に対応しません。

## 使い方

```bash
python app.pyj arg1 arg2                   # ファイルを直接実行
python -c "import mymod"                   # 任意の .pyj モジュールを import（パッケージは __init__.pyj を使えます）

pyj app.pyj arg1 arg2                      # python app.pyj と同じ
pyj -c 'for i in range(3) { print(i) }'    # コマンドラインのコードを実行（python -c と同様）
echo 'if 1 { print("hi") }' | pyj           # 標準入力のコードを実行（pyj - 引数... でも可）

pyj build app.pyj                          # app.py を書き出す
pyj build -c 'def f(x) { return x * 2 }'   # コードを変換した Python を表示（pyj build - は標準入力を読む）
```

`python -m pyj ...` は `pyj ...` と同じです。インストールしなくても、ダウンロードしたファイルを同じように実行できます：`python pyj.py -c '...'`、`python pyj.py build app.pyj`。

- `.pyj` と `.py` のモジュールは互いに import できます。`foo.py` と `foo.pyj` が両方ある場合は `foo.pyj` が優先されます。
- コンパイル結果は `__pycache__/<モジュール名>.pyj.cpython-XY.pyc` にキャッシュされます。ソースファイルか pyj 自体が変わるとキャッシュは無効になります。
- `-c` や標準入力から実行したコードも、ファイルと同じようにエラー位置が示されます。トレースバックにはコードの該当行が表示されます。
- `python app.pyj` の仕組み：Python は起動時に site-packages の `pyj_autoload.pth` を実行します。スクリプトが `.pyj` ファイルだと分かると、プロセスを `python -m pyj app.pyj` に置き換えます（Windows では代わりに子プロセスを起動します）。インタープリターのオプションはそのまま引き継がれます。

Python コードから使う場合：

```python
import pyj
pyj.install_import_hook()                 # .pyj モジュールを import できるようにする
print(pyj.transpile("if x { y() }"))
code = pyj.compile_pyj(src, "file.pyj")   # 位置が .pyj ソースに対応付けられたコードオブジェクト
```

## エラー位置

実行時の例外、構文エラー、`inspect.getsource`、`linecache` のすべてが、`.pyj` ソースの正確な**行と列**を指します。複数の文が 1 行にある場合や、1 つの式が複数行にまたがる場合でも同様です：

```
  File "util.pyj", line 3, in divide
    return a /
           ~~^
           b }
           ~
ZeroDivisionError: division by zero
```

仕組み：変換の際に、pyj は各トークンがソースのどこから来たかを記録します。生成したコードを `ast.parse` で解析し、すべての AST ノードの位置をソース上の位置に書き戻してからコンパイルします。

## 文法

| 規則 | 例 |
|---|---|
| ブロックは `{ }`、インデントは自由 | `while x { x -= 1 }` |
| コロンは省略可能 | `def f(): { ... }` は `def f() { ... }` と同じ |
| 文は `;` で区切る | `a = 1; b = 2` |
| 文が明らかに完結していれば、改行で文が終わる | 1 行に 1 文なら `;` は不要 |
| 括弧の中、または行末の演算子・カンマの後の改行は無視される | `total = 1 +`⏎`2` |
| `.` `,` `and` `or` などで始まる行は前の行の続き | `s = text`⏎`.strip()` |
| `else if` は `elif` の省略形 | `} else if x {` |
| 空のブロックには自動で `pass` が入る | `class E {}` |
| 辞書や集合はいつもどおり書ける | `if k in {1, 2} { d = {} }` |

**ブロックと辞書をどう区別するのか？** `{` がブロックを開くのは、`if/for/while/def/class/try/with/match/case…` 文のヘッダーの末尾にあるとき、つまり名前・数値・文字列・閉じ括弧・`:`、または `else/try/finally/except` の直後にあるときだけです。Python では式の直後に `{` が来ることはあり得ないので、曖昧さはありません。

## 注意点

- `(`、`[`、`-`、`*` で始まる行は前の行の続きに**なりません**。これは、`a`⏎`(b)` が関数呼び出しになってしまう JavaScript の落とし穴を避けるためです。行を続けたい場合は、演算子を行末に置くか、式を括弧で囲んでください。
- `if x: {...}` のように書いた複合文のヘッダーでは、`{` は常にブロックを開きます。1 行の `if` の後に辞書の式を置きたい場合は、通常の `{ }` ブロックで囲んでください。
- コメントは保持されます。式の途中にあるコメントは、その文の行末に移動します。

## 類似プロジェクトとの比較

Python に波括弧を持ち込むという発想のプロジェクトはほかにもあります。pyj はそのいずれとも無関係です。以下の各プロジェクトは、それぞれ自身の変換関数で表の入力を変換し、その結果を実行してテストしました。どの行も再現できます。

### python-with-braces

テストしたバージョン：[python-with-braces](https://pypi.org/project/python-with-braces/) 0.1.2（2026 年 10 月時点の PyPI 最新版）、`PythonWithBraces().process_code()` を使用。

| 入力 | python-with-braces 0.1.2 | pyj |
|---|---|---|
| `d = {"a": 1}` | `d = :"a": 1` に変換され、構文エラー | ✅ |
| ブロック内の入れ子の辞書 | 構文エラー | ✅ |
| `def f(x) { if x { return 1 } else { return 2 } }` | 構文エラー | ✅ |
| `class Myself {`⏎`x = 1`⏎`}` | クラス名が `My` に変わる（クラス定義行の `self` がすべて削除される） | ✅ |
| クラス内の `@staticmethod` | `self` 引数が追加され、インデントも崩れる | ✅ |
| `print("a => b")` | 実行はできるが `a >= b` と表示される（`=>` と `=<` が文字列の中も含めてすべて置き換えられる） | ✅ |
| 実行時の捕捉されない例外 | トレースバックは `<string>` を表示、終了ステータス 0 | トレースバックは `.pyj` ファイルの行と列を表示、終了ステータス 1 |
| `python app.pyj` / モジュールの `import` | 非対応。専用の `pwb` コマンドで実行する | ✅ |

### pybraces

テストしたバージョン：[pybraces](https://pypi.org/project/pybraces/) 0.2.0（2026 年 10 月時点の PyPI 最新版）、`braces2py()` を使用。

pybraces はシェルのワンライナー向けに設計されており、意図的により厳格な独自の文法を採用しています。ブロックは `: {` と書き、改行は空白として扱われるため、文は `;` で区切る必要があります。その文法の範囲では、辞書・入れ子の辞書・クラス・デコレーター・f-string を正しく処理し、同じコードは pyj でもそのまま動きます。違いは次のとおりです：

| | pybraces 0.2.0 | pyj |
|---|---|---|
| コロンなしの `if x { ... }` | 非対応（設計どおり） | ✅ |
| `;` を書かない 1 行 1 文 | 非対応（設計どおり：改行は空白として扱われる） | ✅ |
| `f = lambda: {"a": 1}; print(f())` | 構文エラー：`lambda` の後の `: {` がブロックとして扱われる | ✅ |
| シェルからのコード実行 | `pyb -c CODE`、標準入力、標準モジュールを自動 import する `-M` | `pyj -c CODE`、標準入力 |
| ファイルとモジュール | `pyb FILE` でファイルを実行。このようなファイルの import は非対応 | `python app.pyj`、`import` |
| エラー位置 | 変換後のコードを `python -c` で実行するため、トレースバックは変換後のコードを指す | トレースバックは元のコードを指す |
| 依存関係 | `regex==2024.7.24`。このバージョンには Python 3.14 用のビルド済み wheel がないため、インストールに C コンパイラが必要 | なし |

### その他

[mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace)（2018）は Python 2 による行単位の変換ツールです。`{` は行末に、`}` は単独の行に置く必要があり、実行前にファイルを `.py` に変換しなければなりません。[Bython](https://github.com/mathialo/bython) はより早い時期の先行プロジェクトですが、ここでは比較していません。

## 開発

```bash
python -m unittest discover -s tests -v
```

## ライセンス

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
