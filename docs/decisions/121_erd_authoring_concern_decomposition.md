# 121 - ERD Authoring Concern Decomposition

## Context

- `src/gui/erd/authoring.py` reached 700 LOC and mixed multiple mutation concerns.
- ERD authoring behavior is consumed through compatibility paths (`src.erd_designer`, `src.gui_tools.erd_designer_view`, `src.gui_v2.commands`) and required strict no-behavior-change parity.
- This slice targeted readability/navigation improvements with low GUI lifecycle risk.

## Decision

- Decompose ERD authoring logic into concern modules:
  - `src/gui/erd/authoring_tables.py`
  - `src/gui/erd/authoring_columns.py`
  - `src/gui/erd/authoring_relationships.py`
  - `src/gui/erd/authoring_rename_refs.py`
- Convert `src/gui/erd/authoring.py` into a thin compatibility facade that re-exports:
  - `new_erd_schema_project`
  - `add_table_to_erd_project`
  - `add_column_to_erd_project`
  - `add_relationship_to_erd_project`
  - `update_table_in_erd_project`
  - `update_column_in_erd_project`
  - `_replace_name_in_list`
  - `_replace_name_in_optional_value`
- Extend import contracts to include the new ERD authoring modules in `tests/test_import_contracts.py`.

## Consequences

- ERD authoring responsibilities are now concern-owned and easier to navigate.
- `src/gui/erd/authoring.py` is now a thin compatibility surface while preserving existing import and behavior contracts.
- Targeted ERD, integration, and isolated GUI suites remain green with no observed behavior regressions.
