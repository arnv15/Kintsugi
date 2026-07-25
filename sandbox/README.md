# Kintsugi Seeded Bug sandbox

This package contains six deliberately incorrect Python functions: two Seeded
Bugs for each Root Cause Class selected in ADR-0004.

The `baseline` tag is the immutable starting point for every Run. Create a fresh
worktree from that tag before attempting one bug, as required by ADR-0011:

```sh
git worktree add --detach /tmp/kintsugi-run baseline
cd /tmp/kintsugi-run
python3 -m unittest sandbox.tests.test_scheduling -v
```

The six tests are intentionally red at `baseline`. A Run should select and fix
one test, leaving the other five failures untouched.
