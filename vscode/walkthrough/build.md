# Turn it into plain Python

**Convert to Python (.py)** writes `hello.py` next to `hello.pyj` and opens it beside your code:

```python
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

Same as `pyj build hello.pyj` in a terminal. You can stop using pyj any time.
