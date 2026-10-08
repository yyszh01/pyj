# pyj — 用花括号写 Python

[![CI](https://github.com/yyszh01/pyj/actions/workflows/ci.yml/badge.svg)](https://github.com/yyszh01/pyj/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybrace)](https://pypi.org/project/pybrace/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[English](https://github.com/yyszh01/pyj/blob/main/README.md) | 简体中文

不用管换行和缩进，像 JS 一样写 Python。`.pyj` 文件在运行时透明地转换成标准 Python，报错直接指回 `.pyj` 源码的行号和列号。
```python
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

if n < 0 { print("负数") } else if n == 0 { print("零") }
    else { print("正数") }
```

## 特点

- **单文件、零依赖**：整个工具就是一个 `pyj.py`，只用标准库。
- **透明运行**：安装后 `python app.pyj` 直接跑，任何程序都能 `import` `.pyj` 模块，`.py` 和 `.pyj` 可以混用。
- **报错指回源码**：traceback、语法错误、`inspect.getsource` 都显示 `.pyj` 源码的行和列。
- **字典、集合照常写**：能自动区分代码块的 `{` 和字面量的 `{`。
- **跨平台**：Python 3.10+，在 Linux / macOS / Windows 上由 CI 测试。

## 安装

### 用 pip 安装（推荐）

```bash
pip install pybrace
```

装好后当前 Python 环境里的所有进程都自动支持 `.pyj`，`pip uninstall pybrace` 即可完全移除。PyPI 上的包名是 `pybrace`，模块名和命令仍然是 `pyj`。本项目与名字相近的 [mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace) 无关。

```bash
python app.pyj arg1 arg2           # 直接运行
python -c "import mymod"           # import 任意 .pyj 模块，包可以用 __init__.pyj
pyj build app.pyj                  # 转成 app.py
```

- `.pyj` 和 `.py` 可以互相 import；同名时 `.pyj` 优先。
- 编译结果缓存在 `__pycache__/<模块名>.pyj.cpython-XY.pyc`；源文件或 pyj 本身改动后会自动失效。
- `python app.pyj` 的原理：Python 启动时会执行 site-packages 中的 `pyj_autoload.pth`，它发现启动的是 `.pyj` 文件，就把进程替换成 `python -m pyj app.pyj`（Windows 上是启动子进程），解释器参数原样保留。

### 安装到个人目录（不需要管理员权限）

```bash
pip install --user pybrace
```

包会装进你个人的 site-packages（运行 `python3 -m site --user-site` 可以看到具体位置），不改动系统目录，也不需要 `sudo`。装好后，你这个账号下系统自带的 `python3` 就支持 `.pyj`，`python3 app.pyj` 和 `import` 都能直接用。

**Debian、Ubuntu 等把系统 Python 标记为“外部管理”的发行版**（[PEP 668](https://peps.python.org/pep-0668/)）会报 `error: externally-managed-environment`，加上 `--break-system-packages` 即可：

```bash
pip install --user --break-system-packages pybrace
pip uninstall --break-system-packages pybrace      # 卸载
```

这个参数名字听着吓人，但和 `--user` 一起用时仍然只写入你的个人目录。pybrace 没有任何依赖，不会和 apt 管理的包冲突。

在 Linux 上，`pyj` 命令会装到 `~/.local/bin`（任何系统上都可以用 `python3 -m site --user-base` 查看基础目录）。如果终端提示找不到 `pyj`，把这个目录加进 `PATH`，例如在 `~/.bashrc` 里加一行 `export PATH="$HOME/.local/bin:$PATH"`。`python3 app.pyj` 不受影响，不加也能用。

**不用 pip：** 下载单个文件，装到个人目录。安装记录的是 `pyj.py` 当前的位置，之后别删除或移动它：

```bash
curl -O https://raw.githubusercontent.com/yyszh01/pyj/main/pyj.py
python3 pyj.py install       # 在个人 site-packages 写入 pyj_autoload.pth
python3 pyj.py uninstall     # 卸载
```

### “外部管理”系统上的其他办法

```bash
# 虚拟环境（项目开发推荐）：只有这个 venv 支持 .pyj
python3 -m venv .venv && . .venv/bin/activate && pip install pybrace

# pipx 只提供 pyj 命令：`pyj app.pyj` 能用，
# 但 `python3 app.pyj` 和 import 不支持 .pyj
pipx install pybrace
```

### 只下载单个文件

把 `pyj.py` 放到任意位置即可：

```bash
python pyj.py install     # 写入 pyj_autoload.pth，效果同 pip 安装（在 venv 中运行则只装进该 venv）
python pyj.py uninstall   # 卸载
```

### 不安装也能用

```bash
python3 pyj.py run  app.pyj [参数...]   # 或 python3 pyj.py app.pyj
python3 pyj.py build app.pyj            # 生成 app.py
python3 pyj.py build app.pyj -o -       # 输出到终端
```

在 Python 代码里使用：

```python
import pyj
pyj.install_import_hook()          # 之后可以 import .pyj 模块
print(pyj.transpile("if x { y() }"))
code = pyj.compile_pyj(src, "file.pyj")   # 位置已映射回源码的 code 对象
```

## 报错定位

运行时异常、语法错误、`inspect.getsource`、`linecache` 都直接指向 `.pyj` 源码的**行号和列号**，即使多条语句写在同一行、一个表达式跨了多行也一样准确：

```
  File "util.pyj", line 3, in 除法
    return a /
           ~~^
           b }
           ~
ZeroDivisionError: division by zero
```

原理：转译时记录每个记号在生成代码和源码中的位置，用 `ast.parse` 解析生成的代码后，把每个 AST 节点的位置改写回源码位置，再编译。

## 语法规则

| 规则 | 示例 |
|---|---|
| 代码块用 `{ }`，缩进随意 | `while x { x -= 1 }` |
| 冒号可写可不写 | `def f(): { ... }` 等同 `def f() { ... }` |
| 语句用 `;` 分隔 | `a = 1; b = 2` |
| 换行时语句明显结束会自动断句 | 每行一条语句可以省略 `;` |
| 括号里、或行尾是运算符/逗号时，换行被忽略 | `total = 1 +`⏎`2` |
| 下一行以 `.` `,` `and` `or` 等开头时接上一行 | `s = text`⏎`.strip()` |
| `else if` 是 `elif` 的语法糖 | `} else if x {` |
| 空代码块自动补 `pass` | `class E {}` |
| 字典/集合照常写 | `if k in {1, 2} { d = {} }` |

**如何区分代码块和字典？** 只有当 `{` 出现在 `if/for/while/def/class/try/with/match/case…` 语句头部末尾（前面是名字、数字、字符串、右括号、`:`，或 `else/try/finally/except`）时才是代码块。在 Python 里 `表达式 {` 本来就不合法，所以不会产生歧义。

## 注意事项

- 下一行以 `(`、`[`、`-`、`*` 开头时**不会**接到上一行（避免 JS 那种 `a`⏎`(b)` 被当成函数调用的坑）。需要时把运算符放在行尾，或用括号包起来。
- 复合语句头部写成 `if x: {...}` 时，`{` 总被当成代码块；如果真想在单行 `if` 后写一个字典表达式语句，请用普通的 `{ }` 块包一层。
- 注释会保留；表达式中间的注释会被移到该语句行尾。

## 与同类项目的对比

还有其他项目也想让 Python 用上花括号，pyj 与它们都没有关系。下面的对比基于 python-with-braces 0.1.2（截至 2026 年 10 月 PyPI 上的最新版本）：用它自己的 `PythonWithBraces().process_code()` 转换每段输入，再运行转换结果。每一行都可以用表中的输入自己复现。

| 输入 | [python-with-braces](https://pypi.org/project/python-with-braces/) 0.1.2 | pyj |
|---|---|---|
| `d = {"a": 1}` | 转换成 `d = :"a": 1`，语法错误 | ✅ |
| 代码块里有嵌套字典 | 语法错误 | ✅ |
| `def f(x) { if x { return 1 } else { return 2 } }` | 语法错误 | ✅ |
| `class Myself { x = 1 }` | 类名变成 `My`（类定义行里的 `self` 全被删掉） | ✅ |
| 类里的 `@staticmethod` | 被加上 `self` 参数，缩进也乱了 | ✅ |
| `print("a => b")` | 能运行，但输出 `a >= b`（所有 `=>`、`=<` 都会被替换，字符串里的也是） | ✅ |
| 运行时出现未捕获的异常 | traceback 显示 `<string>`；退出码 0 | traceback 指向 `.pyj` 文件的行和列；退出码 1 |
| `python app.pyj` / `import` 模块 | 不支持，要通过它的 `pwb` 命令运行 | ✅ |

[mayank-verma048/PyBrace](https://github.com/mayank-verma048/PyBrace)（2018）是一个基于 Python 2 的按行转换器：`{` 必须在行尾、`}` 必须单独一行，而且要先转成 `.py` 才能运行。

## 开发

```bash
python -m unittest discover -s tests -v
```

## 许可证

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
