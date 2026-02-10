# Context
- Task requested finishing Direction 3 with no regressions and clear validation behavior.
- Authoritative roadmap identified remaining Direction 3 phase work: deprecate GUI `float` authoring while preserving legacy JSON compatibility.

# Decision
- Removed `float` from GUI dtype authoring options (`DTYPES`).
- Added explicit defensive validation in GUI column-add flow to reject forced `dtype='float'` values with an actionable fix hint to use `decimal`.
- Updated tests to assert GUI dtype options no longer include `float` and to verify forced GUI float authoring is blocked without mutating schema state.
- Updated canon/roadmap documents to reflect Direction 3 phase completion.

# Consequences
- New GUI-authored columns use Direction 3 canonical numeric dtype (`decimal`) instead of legacy `float`.
- Existing `float` schemas still load, validate, generate, and export as before.
- GUI errors are now clearer for invalid/deprecated dtype authoring attempts.
