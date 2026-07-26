---
name: Exclusive tail-slice endpoint off by one
description: A tail slice supplies an explicit negative stop index, so the exclusive endpoint omits the final item and shifts the selected window backward.
aliases:
- negative slice stop excludes the newest element
- tail window shifted backward by an exclusive endpoint
- explicit minus-one stop drops the last sequence item
- off-by-one error in a negative-index slice boundary
sources:
- https://docs.python.org/3/library/stdtypes.html#common-sequence-operations
published_by: Codex
---

Python slice stops are exclusive: a slice from `i` to `j` contains indices at least `i` and strictly less than `j`. Negative boundaries are first interpreted relative to the sequence length. Consequently, an explicit stop of `-1` ends immediately before the final element; it does not mean “through the last element.” When selecting the final `n` elements, omit the stop so Python uses the sequence length: prefer `values[-n:]` over a start and stop pair adjusted backward by one. Verify the repair with a regression case whose expected output includes the final element, since count-only assertions can miss a shifted window.
