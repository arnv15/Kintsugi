---
name: Repair Mutable Defaults
description: Replace stateful default arguments with per-call values.
aliases:
  - shared default argument
  - state leaks between function calls
  - reused list or dictionary default
sources:
  - https://docs.python.org/3/tutorial/controlflow.html#default-argument-values
  - https://docs.python.org/3/reference/compound_stmts.html#function-definitions
---

# Repair Mutable Defaults

Default argument expressions are evaluated when a function is defined. A
mutable value created there is therefore shared by every call that omits that
argument.

Use an immutable sentinel as the default. Inside the function, allocate a fresh
collection whenever the caller did not provide one. Preserve explicitly supplied
collections instead of replacing them.

```python
def collect(value, items=None):
    if items is None:
        items = []
    items.append(value)
    return items
```
