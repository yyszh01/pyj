# pyj — Python with braces

[![CI](https://github.com/yyszh01/pyj/actions/workflows/ci.yml/badge.svg)](https://github.com/yyszh01/pyj/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybrace)](https://pypi.org/project/pybrace/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

English | [简体中文](https://github.com/yyszh01/pyj/blob/main/README.zh-CN.md) | [日本語](https://github.com/yyszh01/pyj/blob/main/README.ja.md)

Write Python like JavaScript: blocks in `{ }`, statements separated by `;` or newlines, and no significant whitespace. `.pyj` files are converted to standard Python transparently at import and run time, and errors point back to the original `.pyj` lines and columns.

```python
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

if n < 0 { print("negative") } else if n == 0 { print("zero") }
    else { print("positive") }
```

## Features

- **Single file, zero dependencies**: the whole tool is one `pyj.py` that uses only the standard library, and it installs itself without pip or root.
- **Transparent execution**: once installed, `python app.pyj` just works, any program can `import` a `.pyj` module, and `.py` and `.pyj` files can be mixed freely.
- **Shell one-liners too**: `pyj -c 'for i in range(3) { print(i) }'`, or pipe code into `pyj`.
- **Errors point to your source**: tracebacks, syntax errors and `inspect.getsource` all show `.pyj` lines and columns.
- **Dicts and sets work as usual**: pyj tells a block `{` apart from a literal `{`.
- **Cross-platform**: Python 3.10+, tested in CI on Linux, macOS and Windows.

## Installation

### Debian, Ubuntu and other systems where pip is restricted

No pip, no `sudo`, no special flags. Three commands:

```bash
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install
rm pyj.py
```

`install` copies pyj into your user site-packages, enables `.pyj` support for every `python3` you run, and adds the `pyj` command to `~/.local/bin`. The downloaded file is no longer needed. If your shell cannot find `pyj`, add `~/.local/bin` to `PATH` (e.g. `export PATH="$HOME/.local/bin:$PATH"` in `~/.bashrc`); `python3 app.pyj` works without it.

To upgrade, repeat the three commands. To remove: `pyj uninstall`. Run inside an activated virtual environment, `install` puts pyj into that environment instead.

### With pip

```bash
pip install pybrace
```

After installing, every Python process in that environment understands `.pyj` files, and `pip uninstall pybrace` removes it completely. The package is named `pybrace` on PyPI, but the module and the command are both `pyj`. It is not affiliated with [mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace), an unrelated project with a similar name.

On systems that mark the system Python as externally managed ([PEP 668](https://peps.python.org/pep-0668/)), `pip install` fails with `error: externally-managed-environment`. Use the installer above, or one of these:

```bash
# Into your user directory; with --user the flag still only writes to ~/.local,
# and pybrace has no dependencies that could conflict with apt
pip install --user --break-system-packages pybrace

# A virtual environment (recommended for projects): only that venv supports .pyj
python3 -m venv .venv && . .venv/bin/activate && pip install pybrace
```

`pipx install pybrace` also works but gives you only the `pyj` command: plain `python3 app.pyj` and imports do not support `.pyj` that way.

## Usage

```bash
python app.pyj arg1 arg2                   # run a file directly
python -c "import mymod"                   # import any .pyj module; packages can use __init__.pyj

pyj app.pyj arg1 arg2                      # same as python app.pyj
pyj -c 'for i in range(3) { print(i) }'    # run code from the command line, like python -c
echo 'if 1 { print("hi") }' | pyj           # run code from stdin (or: pyj - args...)

pyj build app.pyj                          # write app.py
pyj build -c 'def f(x) { return x * 2 }'   # print the Python for some code (pyj build - reads stdin)
```

`python -m pyj ...` is the same as `pyj ...`. Without installing, run the downloaded file the same way: `python pyj.py -c '...'`, `python pyj.py build app.pyj`.

- `.pyj` and `.py` modules can import each other. If both `foo.py` and `foo.pyj` exist, `foo.pyj` wins.
- Compiled code is cached in `__pycache__/<module>.pyj.cpython-XY.pyc`. The cache is invalidated when the source file or pyj itself changes.
- Code run with `-c` or from stdin gets the same error locations as files: the traceback shows the offending line of your code.
- How `python app.pyj` works: at startup Python runs `pyj_autoload.pth` from site-packages. When it sees that the script is a `.pyj` file, it replaces the process with `python -m pyj app.pyj` (on Windows it starts a child process instead). Interpreter flags are preserved.

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

Other projects share the idea of Python with braces. pyj is not affiliated with any of them. Each project below was tested with its own conversion function on the inputs shown, and the result was run; every row can be reproduced.

### python-with-braces

Tested version: [python-with-braces](https://pypi.org/project/python-with-braces/) 0.1.2, the latest release on PyPI as of October 2026, via `PythonWithBraces().process_code()`.

| Input | python-with-braces 0.1.2 | pyj |
|---|---|---|
| `d = {"a": 1}` | Converted to `d = :"a": 1`, a SyntaxError | ✅ |
| A nested dict inside a block | SyntaxError | ✅ |
| `def f(x) { if x { return 1 } else { return 2 } }` | SyntaxError | ✅ |
| `class Myself {`⏎`x = 1`⏎`}` | Class renamed to `My` (every `self` on a class line is removed) | ✅ |
| `@staticmethod` inside a class | A `self` parameter is added and the indentation breaks | ✅ |
| `print("a => b")` | Runs, but prints `a >= b` (`=>` and `=<` are rewritten everywhere, including inside strings) | ✅ |
| Uncaught exception at run time | Traceback shows `<string>`; exit status 0 | Traceback shows the `.pyj` file, line and column; exit status 1 |
| `python app.pyj` / `import` a module | Not supported; run through its `pwb` command | ✅ |

### pybraces

Tested version: [pybraces](https://pypi.org/project/pybraces/) 0.2.0, the latest release on PyPI as of October 2026, via `braces2py()`.

pybraces is designed for shell one-liners and uses its own, deliberately stricter syntax: blocks are written `: {`, and newlines count as spaces, so statements must be separated by `;`. Within that syntax it worked correctly on dicts, nested dicts, classes, decorators and f-strings, and pyj runs the same code unchanged. The differences:

| | pybraces 0.2.0 | pyj |
|---|---|---|
| `if x { ... }` without the colon | Not supported (by design) | ✅ |
| One statement per line without `;` | Not supported (by design: newlines are spaces) | ✅ |
| `f = lambda: {"a": 1}; print(f())` | SyntaxError: the `: {` after `lambda` is taken as a block | ✅ |
| Code from the shell | `pyb -c CODE`, stdin, and `-M` to auto-import standard modules | `pyj -c CODE`, stdin |
| Files and modules | Runs a file with `pyb FILE`; `.pyj`-style imports are not supported | `python app.pyj`, `import` |
| Error locations | Runs the converted code with `python -c`, so tracebacks refer to the converted code | Tracebacks point to the original code |
| Dependencies | `regex==2024.7.24`, which has no prebuilt wheel for Python 3.14, so installing there needs a C compiler | None |

### Others

[mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace) (2018) is a Python 2 line-based converter: `{` must end a line and `}` must stand on its own line, and files must be converted to `.py` before running. [Bython](https://github.com/mathialo/bython) is earlier prior art; it is not compared here.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
