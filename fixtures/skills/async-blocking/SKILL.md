---
name: Move Blocking Work Off the Event Loop
description: Keep synchronous I/O from blocking asynchronous tasks.
aliases:
  - blocking call in async code
  - synchronous work stalls coroutines
  - event loop blocked by file operation
sources:
  - https://docs.python.org/3/library/asyncio-task.html#running-in-threads
---

# Move Blocking Work Off the Event Loop

Calling blocking I/O directly from a coroutine prevents the event loop from
scheduling other tasks until that call returns.

Move the blocking operation to a worker thread with the runtime's supported
thread bridge, then await its result from the coroutine.

```python
result = await asyncio.to_thread(blocking_operation, argument)
```
