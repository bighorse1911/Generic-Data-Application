# 004 — Fix duplicated `normal` generator

Date: 2026-02-08

Summary
- The `generators.py` file accidentally defined the `normal` generator twice. The second definition overwrote the first, removing parameter handling for `min`/`max` clamps and other behavior.

Decision
- Remove the duplicated, simplified `normal` implementation and keep the earlier, fully-featured version that supports `min`, `max`, `decimals`, and clamping.

Consequences
- Behavior is restored for fixtures and tests relying on clamping and decimal control.
- Add tests to prevent regression.
