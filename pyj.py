"""pyj: write Python with braces and semicolons, transpiled to standard Python.

Syntax:
  * Blocks are wrapped in { } instead of relying on indentation; the colon is optional:
        if x > 0 { print(x) } else if x < 0 { print(-x) } else { pass }
  * Statements are separated by ;. A newline also ends a statement when the
    statement is clearly complete (similar to JavaScript's ASI).
  * Newlines inside brackets, or after a trailing operator or comma, are ignored.
  * `else if` is shorthand for `elif`.
  * Dict and set literals use { } as usual: only a { that ends a compound
    statement header opens a block.
"""

import bisect
import importlib.machinery
import importlib.util
import marshal
import os
import sys

__version__ = "0.1.4"

__all__ = ["transpile", "compile_pyj", "run_file", "PyjSyntaxError", "install_import_hook"]

INDENT = "    "

# Statements starting with these keywords can have a block
COMPOUND = {"if", "elif", "else", "for", "while", "def", "class", "try",
            "except", "finally", "with", "async", "match", "case"}
# A block's { may directly follow these keywords
BLOCK_KW = {"else", "try", "finally", "except"}
# A statement cannot end with these keywords, so a newline after them does not end it
NO_END_KW = {"and", "or", "not", "in", "is", "if", "elif", "else", "for", "while",
             "with", "def", "class", "lambda", "import", "from", "as", "del",
             "global", "nonlocal", "assert", "await", "async", "try", "except",
             "finally"}
# A line starting with one of these tokens continues the previous line
CONT_START = {".", ",", ":", "=", "==", "!=", "<", ">", "<=", ">=", "+=", "-=",
              "*=", "/=", "//=", "%=", "**=", "&=", "|=", "^=", ">>=", "<<=",
              "@=", "->", ":=", "**", "//", "/", "%", "&", "|", "^", "<<", ">>",
              "and", "or", "in", "is", "as"}

OPERATORS = sorted([
    "**=", "//=", ">>=", "<<=", "...", "->", ":=", "==", "!=", "<=", ">=",
    "**", "//", "<<", ">>", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "@=", "+", "-", "*", "/", "%", "@", "&", "|", "^", "~", "<", ">", "(",
    ")", "[", "]", "{", "}", ",", ":", ".", ";", "=", "!",
], key=len, reverse=True)

STRING_PREFIXES = {"r", "u", "b", "f", "t", "br", "rb", "fr", "rf", "tr", "rt"}


class PyjSyntaxError(SyntaxError):
    pass


class Token:
    __slots__ = ("kind", "text", "start", "end", "line", "col", "nl_before")

    def __init__(self, kind, text, start, end, line, col, nl_before):
        self.kind = kind          # NAME / NUMBER / STRING / OP / COMMENT
        self.text = text
        self.start = start
        self.end = end
        self.line = line
        self.col = col
        self.nl_before = nl_before

    def __repr__(self):
        return f"Token({self.kind}, {self.text!r}, {self.line}:{self.col})"


# ---------------------------------------------------------------- lexer

class Lexer:
    def __init__(self, src, filename="<pyj>"):
        self.src = src
        self.filename = filename
        self.pos = 0
        self.line_starts = [0]
        for i, ch in enumerate(src):
            if ch == "\n":
                self.line_starts.append(i + 1)

    def loc(self, pos):
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, pos - self.line_starts[lo] + 1

    def error(self, msg, pos):
        line, col = self.loc(pos)
        text = self.src.splitlines()[line - 1] if self.src.splitlines() else ""
        return PyjSyntaxError(msg, (self.filename, line, col, text))

    def tokens(self):
        src, n = self.src, len(self.src)
        out = []
        nl = True
        while True:
            # skip whitespace and line continuations
            while self.pos < n:
                ch = src[self.pos]
                if ch == "\n":
                    nl = True
                    self.pos += 1
                elif ch in " \t\r\f":
                    self.pos += 1
                elif ch == "\\" and src.startswith("\n", self.pos + 1):
                    self.pos += 2
                elif ch == "\\" and src.startswith("\r\n", self.pos + 1):
                    self.pos += 3
                else:
                    break
            if self.pos >= n:
                return out
            start = self.pos
            ch = src[start]
            if ch == "#":
                end = src.find("\n", start)
                end = n if end == -1 else end
                kind = "COMMENT"
                self.pos = end
            elif ch in "\"'":
                self.scan_string(start, "")
                kind = "STRING"
            elif ch.isdigit() or (ch == "." and start + 1 < n and src[start + 1].isdigit()):
                self.scan_number()
                kind = "NUMBER"
            elif ch == "_" or ch.isidentifier():
                p = start + 1
                while p < n and (src[p] == "_" or ("a" + src[p]).isidentifier()):
                    p += 1
                word = src[start:p]
                if p < n and src[p] in "\"'" and word.lower() in STRING_PREFIXES:
                    self.scan_string(p, word.lower())
                    kind = "STRING"
                else:
                    self.pos = p
                    kind = "NAME"
            else:
                for op in OPERATORS:
                    if src.startswith(op, start):
                        break
                else:
                    raise self.error(f"invalid character {ch!r}", start)
                if op == "!":
                    raise self.error("'!' is not supported; use 'not'", start)
                self.pos = start + len(op)
                kind = "OP"
            line, col = self.loc(start)
            out.append(Token(kind, src[start:self.pos], start, self.pos, line, col, nl))
            nl = False

    def scan_number(self):
        src, n, p = self.src, len(self.src), self.pos
        while p < n:
            c = src[p]
            if c.isalnum() or c in "._":
                p += 1
            elif c in "+-" and src[p - 1] in "eE" and not src[self.pos:p].lower().startswith("0x"):
                p += 1
            else:
                break
        self.pos = p

    def scan_string(self, q, prefix):
        """q points at the opening quote; afterwards self.pos is just past the string."""
        src, n = self.src, len(self.src)
        quote = src[q]
        triple = src.startswith(quote * 3, q)
        delim = quote * 3 if triple else quote
        p = q + len(delim)
        is_f = "f" in prefix or "t" in prefix
        while True:
            if p >= n:
                raise self.error("unterminated string literal", q)
            c = src[p]
            if c == "\\":
                p += 2
            elif src.startswith(delim, p):
                self.pos = p + len(delim)
                return
            elif c == "\n" and not triple:
                raise self.error("unterminated string literal (newline in a single-quoted string)", q)
            elif is_f and c == "{":
                if src.startswith("{{", p):
                    p += 2
                else:
                    p = self.scan_fexpr(p + 1)
            else:
                p += 1

    def scan_fexpr(self, p):
        """Scan the expression part of an f-string {...}; return the position after the closing }."""
        src, n = self.src, len(self.src)
        depth = 1
        while p < n:
            c = src[p]
            if c in "\"'":
                self.scan_string(p, "")
                p = self.pos
            elif c == "_" or c.isidentifier():
                s = p
                while p < n and (src[p] == "_" or ("a" + src[p]).isidentifier()):
                    p += 1
                if p < n and src[p] in "\"'" and src[s:p].lower() in STRING_PREFIXES:
                    self.scan_string(p, src[s:p].lower())
                    p = self.pos
            elif c in "{[(":
                depth += 1
                p += 1
            elif c in "}])":
                depth -= 1
                p += 1
                if depth == 0:
                    return p
            else:
                p += 1
        raise self.error("'{' was never closed in f-string", p)


# ---------------------------------------------------------------- transpiler

class Transpiler:
    def __init__(self, src, filename="<pyj>"):
        self.lexer = Lexer(src, filename)
        self.src = src
        self.out = []
        self.spans = []         # (output line index, column, output length, source start, source end)
        self.indent = 0
        self.stmt = []          # tokens of the current statement
        self.comments = []      # comments attached to the current statement
        self.brackets = []      # unclosed ( [ and literal { in the current statement
        self.blocks = []        # one entry per open block: [opening brace token, statements emitted]

    def error(self, msg, tok):
        return self.lexer.error(msg, tok.start)

    # -- predicates

    def is_compound(self):
        return bool(self.stmt) and self.stmt[0].text in COMPOUND and self.stmt[0].kind == "NAME"

    @staticmethod
    def can_end(tok):
        if tok.kind == "NAME":
            return tok.text not in NO_END_KW
        if tok.kind in ("NUMBER", "STRING"):
            return True
        return tok.text in (")", "]", "}", "...")

    def opens_block(self):
        if self.brackets or not self.is_compound():
            return False
        prev = self.stmt[-1]
        if prev.kind == "NAME" and prev.text in BLOCK_KW:
            return True
        return prev.text == ":" or self.can_end(prev)

    # -- output

    def render(self, toks):
        """Join tokens; return (text, position of each token within the text)."""
        parts, spans = [], []
        col = 0
        prev = None
        for t in toks:
            if prev is not None:
                gap = self.src[prev.end:t.start]
                if gap.strip(" \t") != "":
                    gap = "" if prev.text in ("(", "[", "{", ".") or t.text in (")", "]", "}", ",", ".") else " "
                parts.append(gap)
                col += len(gap)
            parts.append(t.text)
            spans.append((col, len(t.text), t.start, t.end))
            col += len(t.text)
            prev = t
        return "".join(parts), spans

    def emit(self, text, spans=(), count=True):
        pad = INDENT * self.indent
        idx = len(self.out)
        self.out.append(pad + text)
        for col, glen, ss, se in spans:
            self.spans.append((idx, len(pad) + col, glen, ss, se))
        if count and self.blocks:
            self.blocks[-1][1] += 1

    def take_comments(self):
        text = "  " + "  ".join(self.comments) if self.comments else ""
        self.comments = []
        return text

    def flush(self):
        if not self.stmt:
            for c in self.comments:
                self.emit(c)
            self.comments = []
            return
        line, spans = self.render(self.stmt)
        self.emit(line + self.take_comments(), spans)
        self.stmt = []

    def open_block(self, tok):
        header, spans = self.render(self.stmt)
        if not header.endswith(":"):
            header += ":"
        self.emit(header + self.take_comments(), spans)
        self.stmt = []
        self.indent += 1
        self.blocks.append([tok, 0])

    def close_block(self, tok):
        self.flush()
        _, count = self.blocks.pop()
        if count == 0:
            # an empty block gets `pass`, mapped to the position of the }
            self.emit("pass", [(0, 4, tok.start, tok.end)], count=False)
        self.indent -= 1

    # -- main loop

    def run(self):
        toks = self.lexer.tokens()
        i = 0
        while i < len(toks):
            tok = toks[i]
            text = tok.text

            if tok.kind == "COMMENT":
                prev = toks[i - 1] if i else None
                if (not self.stmt and prev is not None and prev.text == "{"
                        and prev.line == tok.line and self.blocks and self.blocks[-1][0] is prev
                        and self.blocks[-1][1] == 0):
                    # `if x { # comment` -> keep the comment on the header line
                    self.out[-1] += "  " + text
                elif self.stmt:
                    self.comments.append(text)
                else:
                    self.emit(text, count=False)
                i += 1
                continue

            # automatic statement end: newline + no open brackets + previous token can end a statement + this token is not a continuation
            if (tok.nl_before and self.stmt and not self.brackets
                    and self.can_end(self.stmt[-1])
                    and text not in CONT_START
                    and not (text == "{" and self.is_compound())):
                self.flush()

            if tok.kind == "OP":
                if text == ";":
                    if self.brackets:
                        raise self.error("';' is not allowed inside brackets", tok)
                    self.flush()
                elif text == "{":
                    if self.opens_block():
                        self.open_block(tok)
                    else:
                        self.brackets.append(tok)
                        self.stmt.append(tok)
                elif text in "([":
                    self.brackets.append(tok)
                    self.stmt.append(tok)
                elif text in ")]}":
                    want = {")": "(", "]": "[", "}": "{"}[text]
                    if self.brackets:
                        if self.brackets[-1].text != want:
                            raise self.error(f"closing '{text}' does not match opening '{self.brackets[-1].text}'", tok)
                        self.brackets.pop()
                        self.stmt.append(tok)
                    elif text == "}" and self.blocks:
                        self.close_block(tok)
                    else:
                        raise self.error(f"unmatched '{text}'", tok)
                else:
                    self.stmt.append(tok)
            elif (tok.kind == "NAME" and text == "else" and not self.stmt
                  and i + 1 < len(toks) and toks[i + 1].text == "if"):
                # else if -> elif
                toks[i + 1] = Token("NAME", "elif", tok.start, toks[i + 1].end,
                                    tok.line, tok.col, tok.nl_before)
            else:
                self.stmt.append(tok)
            i += 1

        if self.brackets:
            raise self.error(f"'{self.brackets[-1].text}' was never closed", self.brackets[-1])
        if self.blocks:
            raise self.error("block '{' was never closed", self.blocks[-1][0])
        self.flush()

        gen = "\n".join(self.out) + "\n"
        offsets, acc = [], 0
        for line in self.out:
            offsets.append(acc)
            acc += len(line) + 1
        spans = [(offsets[idx] + col, offsets[idx] + col + glen, ss, se)
                 for idx, col, glen, ss, se in self.spans]
        return gen, SourceMap(gen, self.src, spans)


def _line_starts(text):
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


class SourceMap:
    """Maps positions in the generated code back to positions in the .pyj source."""

    def __init__(self, gen, src, spans):
        spans.sort()
        self.spans = spans
        self.gstarts = [s[0] for s in spans]
        self.gen, self.src = gen, src
        self.gen_starts = _line_starts(gen)
        self.src_starts = _line_starts(src)

    @staticmethod
    def _line(text, starts, lineno):
        s = starts[lineno - 1]
        e = starts[lineno] - 1 if lineno < len(starts) else len(text)
        return s, text[s:e]

    def _src_offset(self, g, end):
        # A start position uses the last token starting at or before g; an end position uses the last token
        # starting before g, so for adjacent tokens such as `a)` the end of `a` is not mapped to the start of `)`.
        i = bisect.bisect_right(self.gstarts, g - 1 if end else g) - 1
        if i < 0:
            return self.spans[0][2] if self.spans else 0
        gs, ge, ss, se = self.spans[i]
        if g <= ge:
            return min(ss + (g - gs), se)
        return se

    def map(self, lineno, col, end=False, byte_col=True):
        """Generated (lineno, col) -> source (lineno, col). Columns are UTF-8 byte offsets by default (the AST convention)."""
        if lineno < 1 or lineno > len(self.gen_starts):
            return lineno, col
        s, line = self._line(self.gen, self.gen_starts, lineno)
        if byte_col and not line.isascii():
            col = len(line.encode()[:col].decode(errors="ignore"))
        p = self._src_offset(s + col, end)
        src_line = bisect.bisect_right(self.src_starts, p)
        s, line = self._line(self.src, self.src_starts, src_line)
        col = p - s
        if byte_col and not line.isascii():
            col = len(line[:col].encode())
        return src_line, col


def transpile(src, filename="<pyj>"):
    """Transpile pyj source code to standard Python source code."""
    return Transpiler(src, filename).run()[0]


def compile_pyj(src, filename="<pyj>", optimize=-1):
    """Compile pyj source to a code object whose error and traceback positions point to the pyj source."""
    import ast
    import linecache

    if not os.path.isfile(filename):
        # lets tracebacks show source lines
        linecache.cache[filename] = (len(src), None, src.splitlines(True), filename)
    gen, smap = Transpiler(src, filename).run()
    try:
        tree = ast.parse(gen, filename)
    except SyntaxError as e:
        raise _map_syntax_error(e, smap, src, filename) from None
    for node in ast.walk(tree):
        if "lineno" not in node._attributes or getattr(node, "lineno", None) is None:
            continue
        node.lineno, node.col_offset = smap.map(node.lineno, node.col_offset)
        if getattr(node, "end_lineno", None) is not None:
            node.end_lineno, node.end_col_offset = smap.map(
                node.end_lineno, node.end_col_offset, end=True)
    return compile(tree, filename, "exec", dont_inherit=True, optimize=optimize)


def _map_syntax_error(e, smap, src, filename):
    lineno, offset = e.lineno or 1, (e.offset or 1)
    line, col = smap.map(lineno, offset - 1, byte_col=False)
    end_line = end_col = None
    if e.end_lineno and e.end_offset:
        end_line, end_col = smap.map(e.end_lineno, e.end_offset - 1, end=True, byte_col=False)
        end_col += 1
    lines = src.splitlines()
    text = lines[line - 1] if 0 < line <= len(lines) else None
    return SyntaxError(e.msg, (filename, line, col + 1, text, end_line, end_col))


# ---------------------------------------------------------------- import hook

class PyjLoader(importlib.machinery.SourceFileLoader):
    """Loads .pyj modules; compiled code is cached in __pycache__/<name>.pyj.<tag>.pyc."""

    def get_code(self, fullname):
        path = self.get_filename(fullname)
        data = self.get_data(path)
        key = importlib.util.source_hash(data + _fingerprint())
        cache = _cache_path(path)
        if cache:
            try:
                with open(cache, "rb") as f:
                    blob = f.read()
                if blob[:4] == importlib.util.MAGIC_NUMBER and blob[4:12] == key:
                    return marshal.loads(blob[12:])
            except (OSError, ValueError, EOFError):
                pass
        code = compile_pyj(importlib.util.decode_source(data), path)
        if cache and not sys.dont_write_bytecode:
            try:
                os.makedirs(os.path.dirname(cache), exist_ok=True)
                tmp = f"{cache}.{os.getpid()}.tmp"
                with open(tmp, "wb") as f:
                    f.write(importlib.util.MAGIC_NUMBER + key + marshal.dumps(code))
                os.replace(tmp, cache)
            except OSError:
                pass
        return code


def _cache_path(path):
    try:
        return importlib.util.cache_from_source(path + ".py")   # foo.pyj -> foo.pyj.<tag>.pyc
    except NotImplementedError:
        return None


_FINGERPRINT = None


def _fingerprint():
    """Cache key component: the cache is invalidated when pyj.py itself changes."""
    global _FINGERPRINT
    if _FINGERPRINT is None:
        try:
            with open(__file__, "rb") as f:
                _FINGERPRINT = f.read()
        except OSError:
            _FINGERPRINT = b""
    return _FINGERPRINT


def install_import_hook():
    """Make every .pyj file on sys.path importable (including packages with __init__.pyj)."""
    if any(getattr(h, "_pyj", False) for h in sys.path_hooks):
        return
    from importlib._bootstrap_external import _get_supported_file_loaders
    hook = importlib.machinery.FileFinder.path_hook(
        (PyjLoader, [".pyj"]), *_get_supported_file_loaders())
    hook._pyj = True
    sys.path_hooks.insert(0, hook)
    sys.path_importer_cache.clear()


def _startup():
    """Called by the .pth file at startup of every Python process."""
    install_import_hook()
    argv = sys.argv
    if argv and argv[0].endswith(".pyj") and os.path.isfile(argv[0]):
        # `python app.pyj`: the interpreter would parse the .pyj file as Python, so run `python -m pyj app.pyj` instead
        orig = getattr(sys, "orig_argv", None) or [sys.executable] + argv
        n = len(argv)
        new = [sys.executable] + orig[1:-n] + ["-m", "pyj"] + orig[-n:]
        if os.name == "posix":
            os.execv(sys.executable, new)
        # Windows has no real exec: start a child process and wait for it; Ctrl+C is left to the child
        import subprocess
        proc = subprocess.Popen(new)
        while True:
            try:
                os._exit(proc.wait())
            except KeyboardInterrupt:
                pass


# ---------------------------------------------------------------- running

def run_source(src, filename, argv, path0="", file=None):
    """Run pyj source as __main__. Returns the exit status (0, or 1 on an uncaught exception)."""
    import builtins
    import traceback
    import types

    sys.argv = list(argv)
    if sys.path:
        sys.path[0] = path0
    install_import_hook()

    mod = types.ModuleType("__main__")
    mod.__builtins__ = builtins
    mod.__spec__ = None
    if file is not None:
        mod.__file__ = file
        mod.__loader__ = PyjLoader("__main__", file)
    sys.modules["__main__"] = mod
    try:
        exec(compile_pyj(src, filename), mod.__dict__)
    except SyntaxError as e:
        traceback.print_exception(type(e), e, None)
        return 1
    except Exception as e:
        # drop pyj's own frames so the traceback looks like plain Python's
        tb = e.__traceback__
        here = os.path.normcase(os.path.abspath(__file__))
        while tb is not None and os.path.normcase(os.path.abspath(tb.tb_frame.f_code.co_filename)) == here:
            tb = tb.tb_next
        if sys.excepthook is sys.__excepthook__:
            # Before 3.13 the default excepthook is implemented in C and reads source lines only from
            # disk, so it cannot see code from -c or stdin registered in linecache; the traceback module can
            traceback.print_exception(type(e), e.with_traceback(tb), tb)
        else:
            sys.excepthook(type(e), e.with_traceback(tb), tb)
        return 1
    return 0


def run_file(path, args=()):
    """Run a .pyj file as __main__, like `python path` does for .py files."""
    path = os.path.abspath(path)
    with open(path, "rb") as f:
        src = importlib.util.decode_source(f.read())
    return run_source(src, path, [path, *args], os.path.dirname(path), file=path)


def run_code(code, args=()):
    """Run pyj code given as a string, like `python -c`."""
    return run_source(code, "<string>", ["-c", *args])


def _read_stdin():
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode()
    return importlib.util.decode_source(data)


# ---------------------------------------------------------------- installation

PTH_NAME = "pyj_autoload.pth"
_MARK = "pyj launcher (created by `pyj install`)"
_SELF_DOC = '"""pyj: write Python with braces'


def _install_dirs():
    """(site-packages, scripts) to install into: the active venv, else the user's own directories."""
    import site
    import sysconfig
    if sys.prefix == sys.base_prefix and site.ENABLE_USER_SITE:
        scheme = sysconfig.get_preferred_scheme("user")
        return site.getusersitepackages(), sysconfig.get_path("scripts", scheme)
    return sysconfig.get_path("purelib"), sysconfig.get_path("scripts")


def _installed_by_pip(site_dir):
    import glob
    return bool(glob.glob(os.path.join(site_dir, "pybrace-*.dist-info")))


def _is_ours(path, marker):
    try:
        with open(path, encoding="utf-8") as f:
            return marker in f.read(4096)
    except (OSError, UnicodeDecodeError):
        return False


def _launcher_path(scripts):
    return os.path.join(scripts, "pyj.cmd" if os.name == "nt" else "pyj")


def _write_launcher(scripts):
    path = _launcher_path(scripts)
    if os.path.exists(path) and not _is_ours(path, _MARK):
        print(f"Skipped the `pyj` command: {path} already exists")
        return None
    os.makedirs(scripts, exist_ok=True)
    if os.name == "nt":
        # `(goto) 2>nul` ends the batch context while the rest of the line still runs, so cmd.exe never reads
        # this file again; `pyj uninstall` can delete it without "The batch file cannot be found".
        # The exit status is Python's.
        text = f'@echo off\r\nrem {_MARK}\r\n(goto) 2>nul & "{sys.executable}" -m pyj %*\r\n'
    else:
        text = f"#!{sys.executable}\n# {_MARK}\nimport sys\nfrom pyj import main\nsys.exit(main())\n"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if os.name != "nt":
        os.chmod(path, 0o755)
    return path


def install():
    """Copy pyj.py into site-packages, add the .pth autoloader and the `pyj` command.

    Without a venv this goes to the user's own directories, so it needs neither
    pip nor root and works on PEP 668 systems such as Debian and Ubuntu.
    """
    import shutil

    site_dir, scripts = _install_dirs()
    if _installed_by_pip(site_dir):
        print(f"pyj is already installed by pip in {site_dir}; nothing to do.")
        return 0
    dst = os.path.join(site_dir, "pyj.py")
    src = os.path.abspath(__file__)
    if os.path.exists(dst) and not _is_ours(dst, _SELF_DOC):
        print(f"Refusing to overwrite {dst}: it is not pyj", file=sys.stderr)
        return 1
    try:
        os.makedirs(site_dir, exist_ok=True)
        if os.path.normcase(dst) != os.path.normcase(src):
            shutil.copyfile(src, dst)
        with open(os.path.join(site_dir, PTH_NAME), "w", encoding="utf-8") as f:
            f.write("import pyj; pyj._startup()\n")
        launcher = _write_launcher(scripts)
    except PermissionError as e:
        print(f"Permission denied: {e.filename}", file=sys.stderr)
        return 1
    print(f"Installed pyj {__version__} into {site_dir}")
    if launcher:
        print(f"Installed the `pyj` command: {launcher}")
        dirs = [os.path.normcase(os.path.abspath(d)) for d in os.environ.get("PATH", "").split(os.pathsep) if d]
        if os.path.normcase(os.path.abspath(scripts)) not in dirs:
            print(f"Note: {scripts} is not on PATH; add it to use the `pyj` command.")
    print("You can now run `python app.pyj` directly, and any Python program can import .pyj modules.")
    print(f"The downloaded {os.path.basename(src)} is no longer needed.")
    return 0


def uninstall():
    site_dir, scripts = _install_dirs()
    if _installed_by_pip(site_dir):
        print("pyj was installed by pip; run `pip uninstall pybrace` instead.", file=sys.stderr)
        return 1
    removed = []
    pth = os.path.join(site_dir, PTH_NAME)
    if os.path.exists(pth):
        os.remove(pth)
        removed.append(pth)
    mod = os.path.join(site_dir, "pyj.py")
    if os.path.exists(mod) and _is_ours(mod, _SELF_DOC):
        os.remove(mod)
        removed.append(mod)
        import glob
        for pyc in glob.glob(os.path.join(site_dir, "__pycache__", "pyj.*.pyc")):
            os.remove(pyc)
    launcher = _launcher_path(scripts)
    if os.path.exists(launcher) and _is_ours(launcher, _MARK):
        os.remove(launcher)
        removed.append(launcher)
    for path in removed:
        print(f"Removed: {path}")
    if not removed:
        print("pyj is not installed")
    return 0


# ---------------------------------------------------------------- command line

def _print_syntax_error(e):
    print(f"{e.filename}:{e.lineno}:{e.offset}: SyntaxError: {e.msg}", file=sys.stderr)
    if e.text:
        print("    " + e.text, file=sys.stderr)
        print("    " + " " * (e.offset - 1) + "^", file=sys.stderr)


USAGE = """\
usage: pyj FILE.pyj [args...]       run a file
       pyj -c CODE [args...]        run code given on the command line
       pyj - [args...]              run code read from stdin (also: `... | pyj`)
       pyj run FILE [args...]       run a file of any name
       pyj build FILE [-o OUT]      convert to Python (OUT '-' means stdout)
       pyj build -c CODE | -        print the Python for code or stdin
       pyj install | uninstall      enable / disable .pyj support for this Python
       pyj -h | --version
"""


def main(argv=None):
    import argparse

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        if sys.stdin is not None and not sys.stdin.isatty():
            return run_source(_read_stdin(), "<stdin>", ["-"])
        sys.stdout.write(USAGE)
        return 2
    first = argv[0]
    if first == "-c":
        if len(argv) < 2:
            print("pyj: -c requires an argument", file=sys.stderr)
            return 2
        return run_code(argv[1], argv[2:])
    if first == "-":
        return run_source(_read_stdin(), "<stdin>", ["-", *argv[1:]])
    if first in ("-h", "--help"):
        sys.stdout.write(USAGE)
        return 0
    if first in ("-V", "--version"):
        print(f"pyj {__version__}")
        return 0
    if first.endswith(".pyj"):
        return run_file(first, argv[1:])     # pyj app.pyj ... is the same as pyj run app.pyj ...

    parser = argparse.ArgumentParser(prog="pyj", usage="pyj {run,build,install,uninstall} ... (see `pyj -h`)", description="Write Python with braces")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run a pyj file")
    p_run.add_argument("file")
    p_run.add_argument("args", nargs=argparse.REMAINDER)
    p_build = sub.add_parser("build", help="convert pyj to Python")
    p_build.add_argument("file", nargs="?", help="input file, or '-' for stdin")
    p_build.add_argument("-c", dest="code", help="convert this code instead of a file")
    p_build.add_argument("-o", "--output", help="output file (default: FILE with .py, or stdout for -c / -)")
    sub.add_parser("install", help="enable .pyj support (user directory, or the active venv)")
    sub.add_parser("uninstall", help="disable .pyj support")
    args = parser.parse_args(argv)

    if args.cmd == "install":
        return install()
    if args.cmd == "uninstall":
        return uninstall()
    if args.cmd == "run":
        return run_file(args.file, args.args)

    if (args.code is None) == (args.file is None):
        parser.error("build needs exactly one of FILE, '-' or -c CODE")
    if args.code is not None:
        src, name, default_out = args.code, "<string>", "-"
    elif args.file == "-":
        src, name, default_out = _read_stdin(), "<stdin>", "-"
    else:
        with open(args.file, "rb") as f:
            src = importlib.util.decode_source(f.read())
        name, default_out = args.file, os.path.splitext(args.file)[0] + ".py"
    try:
        py = transpile(src, name)
    except PyjSyntaxError as e:
        _print_syntax_error(e)
        return 1
    out = args.output or default_out
    if out == "-":
        sys.stdout.write(py)
    else:
        with open(out, "w", encoding="utf-8") as f:
            f.write(py)
    return 0


if __name__ == "__main__":
    # `python pyj.py ...` must run this very file. An installed pyj (possibly an older version) is
    # imported at startup by the .pth file, so replace it with this file and remove its import hook.
    # This also keeps a single module named pyj in the process.
    _here = os.path.normcase(os.path.abspath(__file__))
    _mod = sys.modules.get("pyj")
    if _mod is None or os.path.normcase(os.path.abspath(getattr(_mod, "__file__", "") or "")) != _here:
        sys.path_hooks[:] = [h for h in sys.path_hooks if not getattr(h, "_pyj", False)]
        sys.path_importer_cache.clear()
        _spec = importlib.util.spec_from_file_location("pyj", __file__)
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["pyj"] = _mod
        _spec.loader.exec_module(_mod)
    sys.exit(_mod.main())
