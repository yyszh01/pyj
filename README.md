# pyj — Python with braces

[![CI](https://github.com/yyszh01/pyj/actions/workflows/ci.yml/badge.svg)](https://github.com/yyszh01/pyj/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybrace)](https://pypi.org/project/pybrace/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

English | [简体中文](https://github.com/yyszh01/pyj/blob/main/README.zh-CN.md)

Write Python like JavaScript: blocks in `{ }`, statements separated by `;` or newlines, and no significant whitespace. `.pyj` files are converted to standard Python transparently at import and run time, and errors point back to the original `.pyj` lines and columns.

```python
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

if n < 0 { print("negative") } else if n == 0 { print("zero") }
    else { print("positive") }
```

## Features

- **Single file, zero dependencies**: the whole tool is one `pyj.py` that uses only the standard library.
- **Transparent execution**: once installed, `python app.pyj` just works, any program can `import` a `.pyj` module, and `.py` and `.pyj` files can be mixed freely.
- **Errors point to your source**: tracebacks, syntax errors and `inspect.getsource` all show `.pyj` lines and columns.
- **Dicts and sets work as usual**: pyj tells a block `{` apart from a literal `{`.
- **Cross-platform**: Python 3.10+, tested in CI on Linux, macOS and Windows.

## Installation

### With pip (recommended)

```bash
pip install pybrace
```

After installing, every Python process in that environment understands `.pyj` files. `pip uninstall pybrace` removes it completely. The package is named `pybrace` on PyPI, but the module and the command are both `pyj`. It is not affiliated with [mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace), an unrelated project with a similar name.

```bash
python app.pyj arg1 arg2           # run directly
python -c "import mymod"           # import any .pyj module; packages can use __init__.pyj
pyj build app.pyj                  # convert to app.py
```

- `.pyj` and `.py` modules can import each other. If both `foo.py` and `foo.pyj` exist, `foo.pyj` wins.
- Compiled code is cached in `__pycache__/<module>.pyj.cpython-XY.pyc`. The cache is invalidated when the source file or pyj itself changes.
- How `python app.pyj` works: at startup Python runs `pyj_autoload.pth` from site-packages. When it sees that the script is a `.pyj` file, it replaces the process with `python -m pyj app.pyj` (on Windows it starts a child process instead). Interpreter flags are preserved.

### Install into your user directory (no admin rights)

```bash
pip install --user pybrace
```

This installs into your personal site-packages (`python3 -m site --user-site` prints where) and does not touch system directories or need `sudo`. The system `python3` then supports `.pyj` for your user account: `python3 app.pyj` and imports work directly.

**Debian, Ubuntu and other distributions that mark the system Python as externally managed** ([PEP 668](https://peps.python.org/pep-0668/)) reject this with `error: externally-managed-environment`. Add `--break-system-packages`:

```bash
pip install --user --break-system-packages pybrace
pip uninstall --break-system-packages pybrace      # to remove it
```

Despite its name, together with `--user` this flag still only writes to your user directory. pybrace has no dependencies, so it cannot conflict with packages managed by apt.

The `pyj` command is installed into `~/.local/bin` on Linux (`python3 -m site --user-base` shows the base directory on every OS). If your shell cannot find `pyj`, add that directory to `PATH`, e.g. `export PATH="$HOME/.local/bin:$PATH"` in `~/.bashrc`. `python3 app.pyj` works without it.

**Without pip:** download the single file and install it into your user site-packages. The install refers to `pyj.py` where it is, so keep the file in place:

```bash
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install       # writes pyj_autoload.pth to your user site-packages
python3 pyj.py uninstall     # to remove it
```

### Other options on externally managed systems

```bash
# A virtual environment (recommended for projects): only that venv supports .pyj
python3 -m venv .venv && . .venv/bin/activate && pip install pybrace

# pipx gives you only the `pyj` command: `pyj app.pyj` works,
# but plain `python3 app.pyj` and imports do not
pipx install pybrace
```

### Single file, no pip

Put `pyj.py` anywhere and run:

```bash
python pyj.py install     # writes pyj_autoload.pth; same effect as pip install (inside a venv, only that venv)
python pyj.py uninstall   # undo
```

### Without installing anything

```bash
python pyj.py run app.pyj [args...]    # or: python pyj.py app.pyj
python pyj.py build app.pyj            # writes app.py
python pyj.py build app.pyj -o -       # prints to stdout
```

From Python code:

```python
import pyj
pyj.install_import_hook()                 # .pyj modules become importable
print(pyj.transpile("if x { y() }"))
code = pyj.compile_pyj(src, "file.pyj")   # code object with positions mapped to the .pyj source
```

## Error locations

Runtime exceptions, syntax errors, `inspect.getsource` and `linecache` all point to the exact **line and column** in the `.pyj` source. This holds even when several statements share a line or one expression spans several lines:

```
  File "util.pyj", line 3, in divide
    return a /
           ~~^
           b }
           ~
ZeroDivisionError: division by zero
```

How it works: while converting, pyj records where each token came from in the source. It parses the generated code with `ast.parse`, rewrites every AST node's position back to the source position, and then compiles.

## Syntax

| Rule | Example |
|---|---|
| Blocks use `{ }`; indentation is free-form | `while x { x -= 1 }` |
| The colon is optional | `def f(): { ... }` is the same as `def f() { ... }` |
| Statements are separated by `;` | `a = 1; b = 2` |
| A newline ends a statement when the statement is clearly complete | One statement per line needs no `;` |
| Newlines inside brackets, or after a trailing operator or comma, are ignored | `total = 1 +`⏎`2` |
| A line starting with `.` `,` `and` `or` etc. continues the previous line | `s = text`⏎`.strip()` |
| `else if` is shorthand for `elif` | `} else if x {` |
| Empty blocks get `pass` automatically | `class E {}` |
| Dicts and sets are written as usual | `if k in {1, 2} { d = {} }` |

**How does pyj tell blocks from dicts?** A `{` opens a block only when it ends the header of an `if/for/while/def/class/try/with/match/case…` statement, that is, when it follows a name, number, string, closing bracket, `:`, or `else/try/finally/except`. In Python an expression followed by `{` is never valid, so this is unambiguous.

## Caveats

- A line starting with `(`, `[`, `-` or `*` does **not** continue the previous line. This avoids the JavaScript pitfall where `a`⏎`(b)` becomes a function call. To continue a line, put the operator at the end of the line or wrap the expression in parentheses.
- In a compound statement header written as `if x: {...}`, the `{` always opens a block. To put a dict expression after a one-line `if`, wrap it in a normal `{ }` block.
- Comments are preserved. A comment in the middle of an expression is moved to the end of that statement's line.

## Comparison with similar projects

Other projects share the idea of Python with braces. pyj is not affiliated with any of them. The comparison below was made with python-with-braces 0.1.2 (the latest release on PyPI as of October 2026), using its own `PythonWithBraces().process_code()` to convert each input and then running the result. Every row can be reproduced with the input shown.

| Input | [python-with-braces](https://pypi.org/project/python-with-braces/) 0.1.2 | pyj |
|---|---|---|
| `d = {"a": 1}` | Converted to `d = :"a": 1`, a SyntaxError | ✅ |
| A nested dict inside a block | SyntaxError | ✅ |
| `def f(x) { if x { return 1 } else { return 2 } }` | SyntaxError | ✅ |
| `class Myself { x = 1 }` | Class renamed to `My` (every `self` on a class line is removed) | ✅ |
| `@staticmethod` inside a class | A `self` parameter is added and the indentation breaks | ✅ |
| `print("a => b")` | Runs, but prints `a >= b` (`=>` and `=<` are rewritten everywhere, including inside strings) | ✅ |
| Uncaught exception at run time | Traceback shows `<string>`; exit status 0 | Traceback shows the `.pyj` file, line and column; exit status 1 |
| `python app.pyj` / `import` a module | Not supported; run through its `pwb` command | ✅ |

[mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace) (2018) is a Python 2 line-based converter: `{` must end a line and `}` must stand on its own line, and files must be converted to `.py` before running.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
