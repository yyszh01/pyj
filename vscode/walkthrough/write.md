# Write some pyj

```python
# hello.pyj
def fib(n) { a, b = 0, 1; for _ in range(n) { a, b = b, a + b }; return a }

for i in range(10) {
print(i, fib(i))   # not indented, still inside the loop
}
```

- Blocks are `{ }`; statements end at a newline or `;`
- The colon is optional: `if x {` is the same as `if x: {`
- `else if` means `elif`
- Dicts and sets are written as usual: `d = {"a": 1}`
