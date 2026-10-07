"""pyj: 用花括号和分号书写 Python，转译为标准 Python 代码。

语法规则：
  * 代码块用 { } 包裹，不再依赖缩进；冒号可写可不写：
        if x > 0 { print(x) } else if x < 0 { print(-x) } else { pass }
  * 语句之间用 ; 分隔；换行处如果语句明显已经结束，也会自动断句（类似 JS 的 ASI）。
  * 括号内、或行尾是运算符/逗号时，换行会被忽略，可以随意折行。
  * `else if` 是 `elif` 的语法糖。
  * 字典/集合字面量照常使用 { }：只有出现在复合语句头部末尾的 { 才会被识别为代码块。
"""

import bisect
import importlib.machinery
import importlib.util
import marshal
import os
import sys

__version__ = "0.1.0"

__all__ = ["transpile", "compile_pyj", "run_file", "PyjSyntaxError", "install_import_hook"]

INDENT = "    "

# 以这些关键字开头的语句可以带代码块
COMPOUND = {"if", "elif", "else", "for", "while", "def", "class", "try",
            "except", "finally", "with", "async", "match", "case"}
# 这些关键字后面可以直接跟代码块的 {
BLOCK_KW = {"else", "try", "finally", "except"}
# 以这些关键字结尾时语句不可能结束，换行不断句
NO_END_KW = {"and", "or", "not", "in", "is", "if", "elif", "else", "for", "while",
             "with", "def", "class", "lambda", "import", "from", "as", "del",
             "global", "nonlocal", "assert", "await", "async", "try", "except",
             "finally"}
# 下一行以这些记号开头时，视为上一行的延续
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


# ---------------------------------------------------------------- 词法分析

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
            # 跳过空白和续行符
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
                    raise self.error(f"无法识别的字符 {ch!r}", start)
                if op == "!":
                    raise self.error("不支持单独的 '!'，请使用 not", start)
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
        """q 指向开头引号；扫描结束后 self.pos 指向字符串之后。"""
        src, n = self.src, len(self.src)
        quote = src[q]
        triple = src.startswith(quote * 3, q)
        delim = quote * 3 if triple else quote
        p = q + len(delim)
        is_f = "f" in prefix or "t" in prefix
        while True:
            if p >= n:
                raise self.error("字符串没有结束", q)
            c = src[p]
            if c == "\\":
                p += 2
            elif src.startswith(delim, p):
                self.pos = p + len(delim)
                return
            elif c == "\n" and not triple:
                raise self.error("单行字符串中出现换行", q)
            elif is_f and c == "{":
                if src.startswith("{{", p):
                    p += 2
                else:
                    p = self.scan_fexpr(p + 1)
            else:
                p += 1

    def scan_fexpr(self, p):
        """扫描 f-string 中 {...} 的表达式部分，返回 } 之后的位置。"""
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
        raise self.error("f-string 中的 { 没有闭合", p)


# ---------------------------------------------------------------- 转译

class Transpiler:
    def __init__(self, src, filename="<pyj>"):
        self.lexer = Lexer(src, filename)
        self.src = src
        self.out = []
        self.spans = []         # (输出行号, 行内列, 输出长度, 源起点, 源终点)
        self.indent = 0
        self.stmt = []          # 当前语句的记号
        self.comments = []      # 当前语句附带的注释
        self.brackets = []      # 当前语句内未闭合的 ( [ {字面量
        self.blocks = []        # 每层代码块：[开括号记号, 已输出语句数]

    def error(self, msg, tok):
        return self.lexer.error(msg, tok.start)

    # -- 辅助判断

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

    # -- 输出

    def render(self, toks):
        """拼接记号，返回 (文本, 每个记号在文本中的位置)。"""
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
            # 空代码块补 pass，位置映射到 }
            self.emit("pass", [(0, 4, tok.start, tok.end)], count=False)
        self.indent -= 1

    # -- 主循环

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
                    # `if x { # 注释` -> 注释留在头部那一行
                    self.out[-1] += "  " + text
                elif self.stmt:
                    self.comments.append(text)
                else:
                    self.emit(text, count=False)
                i += 1
                continue

            # 自动断句：换行 + 括号已闭合 + 上一个记号可以结尾 + 当前记号不是延续
            if (tok.nl_before and self.stmt and not self.brackets
                    and self.can_end(self.stmt[-1])
                    and text not in CONT_START
                    and not (text == "{" and self.is_compound())):
                self.flush()

            if tok.kind == "OP":
                if text == ";":
                    if self.brackets:
                        raise self.error("括号内不能出现 ';'", tok)
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
                            raise self.error(f"'{text}' 与 '{self.brackets[-1].text}' 不匹配", tok)
                        self.brackets.pop()
                        self.stmt.append(tok)
                    elif text == "}" and self.blocks:
                        self.close_block(tok)
                    else:
                        raise self.error(f"多余的 '{text}'", tok)
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
            raise self.error(f"'{self.brackets[-1].text}' 没有闭合", self.brackets[-1])
        if self.blocks:
            raise self.error("代码块 '{' 没有闭合", self.blocks[-1][0])
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
    """把生成代码中的位置映射回 .pyj 源码中的位置。"""

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
        # 起点找“起点 <= g 的最后一个记号”；终点找“起点 < g 的最后一个记号”，
        # 这样紧挨着的两个记号（如 `a)`）不会把 a 的终点映射成 ) 的起点。
        i = bisect.bisect_right(self.gstarts, g - 1 if end else g) - 1
        if i < 0:
            return self.spans[0][2] if self.spans else 0
        gs, ge, ss, se = self.spans[i]
        if g <= ge:
            return min(ss + (g - gs), se)
        return se

    def map(self, lineno, col, end=False, byte_col=True):
        """生成代码的 (行号, 列) -> 源码的 (行号, 列)。列默认是 UTF-8 字节偏移（AST 的约定）。"""
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
    """把 pyj 源码转成标准 Python 源码。"""
    return Transpiler(src, filename).run()[0]


def compile_pyj(src, filename="<pyj>", optimize=-1):
    """把 pyj 源码编译成 code 对象；报错和 traceback 的行号、列号都指向 pyj 源码。"""
    import ast
    import linecache

    if not os.path.isfile(filename):
        # 让 traceback 能显示源码行
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


# ---------------------------------------------------------------- import 钩子

class PyjLoader(importlib.machinery.SourceFileLoader):
    """加载 .pyj 模块；编译结果缓存在 __pycache__/<name>.pyj.<tag>.pyc。"""

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
    """pyj.py 本身变了，缓存也要失效。"""
    global _FINGERPRINT
    if _FINGERPRINT is None:
        try:
            with open(__file__, "rb") as f:
                _FINGERPRINT = f.read()
        except OSError:
            _FINGERPRINT = b""
    return _FINGERPRINT


def install_import_hook():
    """安装后，sys.path 中所有 .pyj 文件都能直接 import（包括包里的 __init__.pyj）。"""
    if any(getattr(h, "_pyj", False) for h in sys.path_hooks):
        return
    from importlib._bootstrap_external import _get_supported_file_loaders
    hook = importlib.machinery.FileFinder.path_hook(
        (PyjLoader, [".pyj"]), *_get_supported_file_loaders())
    hook._pyj = True
    sys.path_hooks.insert(0, hook)
    sys.path_importer_cache.clear()


def _startup():
    """由 .pth 文件在每个 Python 进程启动时调用。"""
    install_import_hook()
    argv = sys.argv
    if argv and argv[0].endswith(".pyj") and os.path.isfile(argv[0]):
        # `python app.pyj`：解释器会把 .pyj 当 Python 解析，这里改为执行 `python -m pyj app.pyj`
        orig = getattr(sys, "orig_argv", None) or [sys.executable] + argv
        n = len(argv)
        new = [sys.executable] + orig[1:-n] + ["-m", "pyj"] + orig[-n:]
        if os.name == "posix":
            os.execv(sys.executable, new)
        # Windows 没有真正的 exec：启动子进程并等它结束；Ctrl+C 交给子进程处理
        import subprocess
        proc = subprocess.Popen(new)
        while True:
            try:
                os._exit(proc.wait())
            except KeyboardInterrupt:
                pass


# ---------------------------------------------------------------- 运行

def run_file(path, args=()):
    """像 `python path` 一样把 .pyj 文件作为 __main__ 运行。"""
    import builtins
    import traceback
    import types

    path = os.path.abspath(path) if not os.path.isabs(path) else path
    with open(path, "rb") as f:
        src = importlib.util.decode_source(f.read())
    sys.argv = [path] + list(args)
    sys.path[0] = os.path.dirname(path)
    install_import_hook()

    mod = types.ModuleType("__main__")
    mod.__file__ = path
    mod.__builtins__ = builtins
    mod.__loader__ = PyjLoader("__main__", path)
    mod.__spec__ = None
    sys.modules["__main__"] = mod
    try:
        exec(compile_pyj(src, path), mod.__dict__)
    except SyntaxError as e:
        traceback.print_exception(type(e), e, None)
        return 1
    except Exception as e:
        # 去掉 pyj 自己的栈帧，traceback 看起来和直接运行 Python 一样
        tb = e.__traceback__
        here = os.path.normcase(os.path.abspath(__file__))
        while tb is not None and os.path.normcase(os.path.abspath(tb.tb_frame.f_code.co_filename)) == here:
            tb = tb.tb_next
        sys.excepthook(type(e), e.with_traceback(tb), tb)
        return 1
    return 0


# ---------------------------------------------------------------- 安装

PTH_NAME = "pyj_autoload.pth"


def _site_dirs():
    import site
    import sysconfig
    dirs = [sysconfig.get_paths()["purelib"]]
    if sys.prefix == sys.base_prefix and site.ENABLE_USER_SITE:
        dirs.insert(0, site.getusersitepackages())
    return dirs


def install():
    target = _site_dirs()[0]
    os.makedirs(target, exist_ok=True)
    pth = os.path.join(target, PTH_NAME)
    here = os.path.dirname(os.path.abspath(__file__))
    with open(pth, "w", encoding="utf-8") as f:
        f.write(f"{here}\nimport pyj; pyj._startup()\n")
    print(f"已安装: {pth}")
    print("现在可以直接 `python3 app.pyj` 运行，任何 Python 程序都能 import .pyj 模块。")
    return 0


def uninstall():
    removed = False
    for d in _site_dirs():
        pth = os.path.join(d, PTH_NAME)
        if os.path.exists(pth):
            os.remove(pth)
            print(f"已删除: {pth}")
            removed = True
    if not removed:
        print("没有找到已安装的 pyj")
    return 0


# ---------------------------------------------------------------- 命令行

def _print_syntax_error(e):
    print(f"{e.filename}:{e.lineno}:{e.offset}: 语法错误: {e.msg}", file=sys.stderr)
    if e.text:
        print("    " + e.text, file=sys.stderr)
        print("    " + " " * (e.offset - 1) + "^", file=sys.stderr)


def main(argv=None):
    import argparse

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].endswith(".pyj"):
        return run_file(argv[0], argv[1:])     # pyj app.pyj ... 等同 pyj run app.pyj ...

    parser = argparse.ArgumentParser(prog="pyj", description="用花括号书写 Python")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="转译并运行 .pyj 文件")
    p_run.add_argument("file")
    p_run.add_argument("args", nargs=argparse.REMAINDER)
    p_build = sub.add_parser("build", help="转译为 .py 文件")
    p_build.add_argument("file")
    p_build.add_argument("-o", "--output", help="输出文件，默认同名 .py；'-' 表示标准输出")
    sub.add_parser("install", help="安装到 site-packages：之后所有 Python 进程自动支持 .pyj")
    sub.add_parser("uninstall", help="卸载自动支持")
    args = parser.parse_args(argv)

    if args.cmd == "install":
        return install()
    if args.cmd == "uninstall":
        return uninstall()
    if args.cmd == "run":
        return run_file(args.file, args.args)

    with open(args.file, encoding="utf-8") as f:
        src = f.read()
    try:
        py = transpile(src, args.file)
    except PyjSyntaxError as e:
        _print_syntax_error(e)
        return 1
    out = args.output or os.path.splitext(args.file)[0] + ".py"
    if out == "-":
        sys.stdout.write(py)
    else:
        with open(out, "w", encoding="utf-8") as f:
            f.write(py)
    return 0


if __name__ == "__main__":
    # 统一使用名为 pyj 的模块，避免 __main__ 和 pyj 两份副本各装一个钩子
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import pyj as _pyj
    except ImportError:
        _pyj = None
    finally:
        del sys.path[0]
    sys.exit((_pyj.main if _pyj else main)())
