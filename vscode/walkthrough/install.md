# Install pyj

pyj is one small Python file with no dependencies. The extension uses your Python (3.8 or newer):
the `pyj.pythonPath` setting, else the interpreter selected in the Python extension, else `python3`
(`python` on Windows).

**Install pyj…** offers two ways:

| | When |
|---|---|
| `pip install pybrace` | In a virtual environment, on Windows and on macOS |
| **pyj installer** (no pip) | Debian, Ubuntu and other systems where pip says `externally-managed-environment`. Installs into your user directory, no `sudo` |

The same from a terminal:

```bash
pip install pybrace

# or, without pip
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install
rm pyj.py
```

Afterwards every `python` you run understands `.pyj` files: `python app.pyj` and `import` just work.
