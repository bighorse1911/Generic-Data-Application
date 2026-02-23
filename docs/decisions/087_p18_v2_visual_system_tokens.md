# 087 - P18 V2 Visual System Pass

## Context
- Priority P18 in `NEXT_DECISIONS.md` required consistent v2 visual language across route family screens.
- v2 shell/screens still contained route-local literal colors/fonts/spacing and inconsistent focus/button styling.
- Visual drift risk increased as new v2 routes and header actions were added.

## Decision
- Add shared v2 visual token module: `src/gui_kit/theme_tokens.py`.
  - color roles,
  - typography scale,
  - spacing scale,
  - focus-ring tokens,
  - button hierarchy roles (`primary`, `secondary`, `nav`) with `v2_button_options(...)`.
- Refactor v2 shell and route surfaces to consume shared tokens:
  - `src/gui_v2_redesign.py` (`V2ShellFrame`, `home_v2` card/header styling),
  - `src/gui_v2_schema_project.py` (v2 schema header button/typography/colors),
  - v2 routes inheriting `V2ShellFrame` now receive tokenized nav/header/status/button styling transitively.
- Keep behavior contracts unchanged (navigation/lifecycle/runtime semantics untouched).

## Consequences
- V2 route family visuals now come from one token source and remain easier to evolve safely.
- Focus-ring and button hierarchy behavior are explicit and consistent across v2 navigation/action surfaces.
- Added regression coverage:
  - `tests/test_gui_kit_theme_tokens.py`,
  - `tests/test_gui_v2_visual_system.py`,
  - updated catalog exposure checks in `tests/test_gui_kit_catalog.py`.
