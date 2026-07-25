# Root Cause Classes

Each pair looks different at the public seam but shares one diagnosis and one
fix strategy.

| Root Cause Class | Shared underlying mistake | Shared fix strategy |
| --- | --- | --- |
| DST-boundary datetime arithmetic | Arithmetic on aware datetimes relies on implicit wall-clock or elapsed-time semantics across an offset transition. | Choose the intended time frame explicitly before arithmetic: local calendar time for a wall-clock appointment, UTC for elapsed duration. |
| Money represented as float instead of Decimal | Monetary values enter binary floating-point arithmetic before the cent boundary is settled. | Keep the calculation in `Decimal` and apply an explicit cent-rounding/allocation policy only at the output boundary. |
| `asyncio` exception semantics | Async completion is detached from the caller, so a failed or unfinished operation is treated as a successful result. | Await the operation at the public completion boundary and allow its completion or exception to propagate to the caller. |

The shared strategy is intentionally conceptual rather than a copied patch. A
Skill describes the Root Cause Class without carrying repository code, while
each Run still applies that strategy to the types and control flow it finds.
