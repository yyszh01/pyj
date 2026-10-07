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

装好后当前 Python 环境里的所有进程都自动支持 `.pyj`，`pip uninstall pybrace` 即可完全移除。PyPI 上的包名是 `pybrace`，模块名和命令仍然是 `pyj`。

```bash
python app.pyj arg1 arg2           # 直接运行
python -c "import mymod"           # import 任意 .pyj 模块，包可以用 __init__.pyj
pyj build app.pyj                  # 转成 app.py
```

- `.pyj` 和 `.py` 可以互相 import；同名时 `.pyj` 优先。
- 编译结果缓存在 `__pycache__/<模块名>.pyj.cpython-XY.pyc`；源文件或 pyj 本身改动后会自动失效。
- `python app.pyj` 的原理：Python 启动时会执行 site-packages 中的 `pyj_autoload.pth`，它发现启动的是 `.pyj` 文件，就把进程替换成 `python -m pyj app.pyj`（Windows 上是启动子进程），解释器参数原样保留。

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

## 开发

```bash
python -m unittest discover -s tests -v
```

## 许可证

[MIT](https://github.com/yyszh01/pyj/blob/main/LICENSE)
