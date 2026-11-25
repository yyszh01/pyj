# pyj for VS Code — Python with braces

Language support for [pyj](https://github.com/yyszh01/pyj): Python whose blocks are written in `{ }`, so code keeps working after a chat app, a web form or a template has eaten the whitespace.

```python
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

for i in range(10) {
print(i, fib(i))   # not indented, still inside the loop
}
```

## Features

- **Syntax highlighting** for `.pyj` files, built on VS Code's own Python grammar. Code blocks in `{ }` are told apart from dict and set literals, using the same rule as pyj itself.
- **Editing**: `#` comments (Ctrl+/), bracket and quote auto-closing, auto-indent after `{`, folding by block.
- **Checks that pyj is installed** when you open a `.pyj` file, and **installs it for you** with either pip or the pip-free installer.
- **Run This File** (▷ in the editor title): runs the file in a terminal with your Python; `input()` works and tracebacks point to the `.pyj` lines.
- **Convert to Python (.py)**: writes a plain, indented `.py` next to the `.pyj` and opens it beside it.
- **Get started walkthrough**: *Help → Welcome → Walkthroughs → Get started with pyj*.

## Installing pyj

The extension highlights `.pyj` files on its own. To **run** them you need pyj itself (one small Python file, no dependencies) installed for your Python, **3.8 or newer**.

The easiest way: open a `.pyj` file and click **Install pyj…** in the notification, or run **pyj: Install or Upgrade pyj…** from the Command Palette (Ctrl+Shift+P). It offers two methods:

| Method | Use it when |
|---|---|
| **pip install pybrace** | In a virtual environment, on Windows and on macOS |
| **pyj installer (no pip)** | On Debian, Ubuntu and other systems where `pip install` fails with `error: externally-managed-environment` ([PEP 668](https://peps.python.org/pep-0668/)). Installs into your user directory; no `sudo` |

Or from a terminal:

```bash
# pip (the package is called "pybrace"; the module and the command are "pyj")
pip install pybrace

# without pip: download the installer, run it, delete it
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install
rm pyj.py
```

On Windows without curl, PowerShell does the same:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py -OutFile pyj.py
python pyj.py install
Remove-Item pyj.py
```

After installing, every Python process of that interpreter understands `.pyj`: `python app.pyj` runs a file and `import mymodule` finds `mymodule.pyj`. Check with **pyj: Check Installation**, or `pyj --version` in a terminal (if the shell cannot find `pyj`, add `~/.local/bin` to `PATH`; `python3 app.pyj` works without it).

To remove pyj: `pip uninstall pybrace`, or `pyj uninstall` if you used the installer.

### Which Python does the extension use?

1. The `pyj.pythonPath` setting, if set
2. Otherwise the interpreter selected in the [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (status bar), if that extension is installed
3. Otherwise `python3` (`python` on Windows)

pyj must be installed for that same Python. In a virtual environment, install it into the environment (`pip install pybrace` there).

## Commands

| Command | |
|---|---|
| pyj: Run This File | Run the current `.pyj` in a terminal (also ▷ in the editor title and the editor's context menu) |
| pyj: Convert to Python (.py) | `pyj build` the current file and open the result |
| pyj: Check Installation | Show the Python and pyj versions in use |
| pyj: Install or Upgrade pyj… | Install with pip or with the installer |
| pyj: New pyj File | Open a sample `.pyj` |

## Settings

| Setting | Default | |
|---|---|---|
| `pyj.pythonPath` | `""` | Python to use (see above) |
| `pyj.checkOnOpen` | `true` | Check once per session, when a `.pyj` file is opened, that pyj is installed |

## Feedback

Bugs: [issues](https://github.com/yyszh01/pyj/issues/new/choose). Questions and ideas: [Discussions](https://github.com/yyszh01/pyj/discussions). English, 中文 and 日本語 are all welcome.

## License

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
