# Data Semantics Specification
Generic Data Application

This document defines the canonical meaning of data concepts used in this
project. It is authoritative for:

- Generator logic
- Schema validation
- JSON schema authoring
- AI-assisted feature implementation
- Invariant tests

If behavior is unclear, this document overrides assumptions.
If you make updates to any DATA_SEMANTICS in the project, update this file too.

## Implementation status (2026-02-10)

Direction 3 (float -> decimal) is completed.

- Runtime support today: `int`, `decimal`, legacy `float`, `text`, `bool`, `date`, `datetime`, `bytes`
- Canonical authoring dtypes: `int`, `decimal`, `text`, `bool`, `date`, `datetime`, `bytes`
- Backward compatibility policy: existing JSON schemas using `float` remain supported.
- GUI authoring policy: new columns use `decimal`; GUI blocks new `float` column creation.
- SCD Type 1 and Type 2 are implemented in generator + validator + JSON IO + GUI authoring controls (business-key linkage, tracked slowly-changing columns, and SCD2 active periods).
- Business-key behavior controls are implemented end-to-end:
  - `business_key_static_columns` for attributes that must remain stable per business key across versions,
  - `business_key_changing_columns` for attributes that are expected to change per business key across versions.
- GUI-only update (2026-02-12): column edit workflow and kit dark mode were added without changing canonical data semantics.
- GUI-only update (2026-02-12): generation behavior guide page added to explain configuration patterns without changing canonical data semantics.
- GUI-only update (2026-02-14): column editor now filters generators by selected dtype and provides pattern presets + generator params templates without changing canonical data semantics.
- GUI-only update (2026-02-14): kit screens now use the regular/default Tk/ttk theme (dark mode disabled) without changing canonical data semantics.
- GUI-only update (2026-02-14): phase-A gui_kit QoL primitives (toasts, debounced search, token editors, params JSON editor, shortcuts help) were integrated without changing canonical data semantics.
- GUI-only update (2026-02-14): phase-B gui_kit UX primitives (preview pagination, preview column chooser, inline validation summary jumps, and dirty-state prompts) were integrated without changing canonical data semantics.
- GUI-only update (2026-02-14): phase-C legacy-screen adoption now exposes the same Phase B preview/validation/dirty-state UX patterns in `schema_project_legacy` without changing canonical data semantics.
- Priority 1 update (2026-02-14): time-aware constraints phase 2 implemented via `time_offset` generator + validator + GUI authoring exposure.
- Priority 1 update (2026-02-14): hierarchical categories phase 3 implemented via `hierarchical_category` generator + validator + GUI authoring exposure.
- Priority 1 update (2026-02-14): SCD2 now supports incoming-FK child tables with FK-capacity-aware version growth.
- Priority 1 rollout status: phases 1-5 are completed.
- Extensible data types update (2026-02-14): `bytes` promoted to first-class dtype with validator/runtime/GUI/SQL/CSV support.
- Generator behavior update (2026-02-14): `ordered_choice` implemented for deterministic sequence progression across named order paths with weighted movement.
- Business-key cardinality update (2026-02-14): `business_key_unique_count` now allows configuring unique business keys independently from table row count.
- Generator behavior update (2026-02-14): `sample_csv` now supports optional row-matched sampling via `match_column` + `match_column_index` for same-row correlated CSV values.

## Core design principle

**Dtypes are storage domains.**
All meaning (email, latitude, money, status, etc.) is implemented via
**generator + params + constraints**.

All generation must remain deterministic per `project.seed`.

---

# 1. Foundational Data Types (Storage Domains)

Each `ColumnSpec` has a `dtype`. This defines its portable storage domain.
Generators may refine behavior, but must respect dtype constraints.

## 1.1 int

Definition:
- Whole number (`int`)
- No fractional component

Typical uses:
- Primary keys
- Foreign keys
- Counters (quantity, age, rank)
- Years

Allowed constraints:
- `min_value`, `max_value`

Rules:
- If `primary_key=true`, column must be `nullable=false`, unique, and deterministic.

## 1.2 decimal (canonical numeric dtype)

Definition:
- Decimal numeric domain for non-integer values
- Preferred implementation target is `decimal.Decimal`

Typical uses:
- Money, measurements, rates, percentages
- Geographic coordinates (lat/lon)

Allowed constraints:
- `min_value`, `max_value`
- `scale` (optional decimal places)

Rules:
- Respect configured bounds
- Apply rounding only if configured
- Deterministic per seed

## 1.3 float (legacy compatibility dtype)

Definition:
- Transitional numeric dtype accepted for backward compatibility
- Semantically equivalent to decimal-like numeric fields in existing projects

Rules:
- Existing schema JSON with `dtype="float"` must continue to load and generate.
- New feature work should target decimal semantics, not expand float-only behavior.

## 1.4 text

Definition:
- Arbitrary textual value

Typical uses:
- Names, labels, categories, codes
- Emails, UUIDs, country codes (via generators)

Allowed constraints:
- `min_length`, `max_length`
- `pattern` (regex)
- `choices`
- `weights` (weighted choices)
- `ordered` (ordered categories)

Rules:
- If `choices` is defined, select categorically (uniform unless `weights` provided).
- If `generator="sample_csv"`, selection is empirical from source data.
- Regex constraints must be enforced.

## 1.5 bool

Definition:
- Boolean (`True`/`False`)

Allowed constraints:
- `probability_true` (0.0 to 1.0)

Rules:
- Bernoulli semantics
- Deterministic per seed

## 1.6 date

Definition:
- Calendar date without time
- Stored/exported as ISO 8601 `YYYY-MM-DD`

Allowed constraints:
- `start_date`, `end_date`

## 1.7 datetime

Definition:
- Timestamp with date and time
- Stored/exported as ISO 8601 string
- Timezone behavior is controlled by generator semantics/params

Allowed constraints:
- `start_datetime`, `end_datetime`

## 1.8 bytes (binary dtype)

Definition:
- Binary payload (`bytes`) for blob-like data

Rules:
- CSV exports should encode bytes (for example base64) at export time.
- SQLite storage should map bytes to blob-compatible storage.
- Deterministic generation for bytes columns remains seed-driven.

---

# 2. Semantic Meaning via Generators

Generators define meaning, not dtypes.

Examples:
- Email: `dtype=text`, `generator="email"`
- Latitude: `dtype=decimal|float`, `generator="latitude"`
- Weighted status: `dtype=text`, `generator="weighted_choice"`

Rules:
- Adding a new data meaning should usually add a generator, not a dtype.
- New dtypes are rare and must represent a new storage domain.

### 2.1 Conditional generator (`if_then`) (phase 1 implemented)

Definition:
- Deterministic conditional branch from another column in the same row.

Params:
- `if_column` (required): source column name in same table.
- `operator` (optional): `==` or `!=` (default `==`).
- `value` (required): comparison value.
- `then_value` (required): output when condition is true.
- `else_value` (required): output when condition is false.

Rules:
- `if_column` must exist and must not be the same as the target column.
- Target column must include `if_column` in `depends_on` so generation order is valid.
- `value`, `then_value`, and `else_value` must be scalar JSON values (not objects/lists).
- Validation/runtime errors must include location + issue + fix hint.

### 2.2 Time-aware generator (`time_offset`) (phase 2 implemented)

Definition:
- Deterministic temporal offset from another column in the same row.
- Supports both `date` and `datetime` columns.
- Enforces before/after relative constraints using bounded offsets.

Params:
- `base_column` (required): source column name in same table.
- `direction` (optional): `after` or `before` (default `after`).
- For `date` target columns:
  - `min_days` (optional, default `0`)
  - `max_days` (optional, default `min_days`)
- For `datetime` target columns:
  - `min_seconds` (optional, default `0`)
  - `max_seconds` (optional, default `min_seconds`)

Rules:
- Target column dtype must be `date` or `datetime`.
- `base_column` must exist, must not be the target column itself, and must have the same dtype as target.
- Target column must include `base_column` in `depends_on` so generation order is valid.
- Date columns use day offsets only; datetime columns use second offsets only.
- Offset bounds must be integers, non-negative, and `min <= max`.
- Validation/runtime errors must include location + issue + fix hint.

### 2.3 Hierarchical category generator (`hierarchical_category`) (phase 3 implemented)

Definition:
- Deterministic child-category selection from a parent category column in the same row.
- Encodes parent->children category trees via params JSON.

Params:
- `parent_column` (required): source column name in same table.
- `hierarchy` (required): non-empty object mapping parent values to non-empty child lists.
- `default_children` (optional): fallback child list used when parent value has no explicit mapping.

Rules:
- Target column dtype must be `text`.
- `parent_column` must exist, must not be the target column itself, and must be listed in `depends_on`.
- Child lists must contain scalar JSON values (no objects/lists).
- If parent column has explicit `choices`, each choice must be represented in `hierarchy` unless `default_children` is provided.
- Validation/runtime errors must include location + issue + fix hint.

### 2.4 Ordered choice generator (`ordered_choice`)

Definition:
- Selects one named order path and then progresses through that path over rows.
- Movement along the path is controlled by weighted step sizes.

Params:
- `orders` (required): non-empty object mapping order names to non-empty ordered value lists.
- `order_weights` (optional): object mapping each order name to a non-negative weight.
- `move_weights` (optional): non-empty list of non-negative movement weights; index `0` means stay, `1` means move +1, `2` means move +2, and so on.
- `start_index` (optional): non-negative integer starting position in each order list (default `0`).

Rules:
- Target column dtype must be `text` or `int`.
- `orders` keys must be non-empty strings and must map to scalar JSON value lists.
- If `order_weights` is provided, keys must exactly match `orders` keys and include at least one value > 0.
- `move_weights` must include at least one value > 0.
- `start_index` must be within every configured order length.
- Validation/runtime errors must include location + issue + fix hint.

---

# 3. Identity Concepts

## 3.1 Primary Key (PK)

Definition:
- Surrogate identifier
- `dtype=int`
- `primary_key=true`
- `nullable=false`

Rules:
- Exactly one PK per table
- PK must be unique and never null
- PK must not depend on other columns

## 3.2 Business Key

Definition:
- Real-world unique identifier (natural or synthetic)
- Does not replace PK

Rules:
- Nullable only when explicitly allowed by model semantics.

Optional behavior fields:
- `business_key_static_columns`: non-key attributes that should stay constant for the same business key across records.
- `business_key_changing_columns`: non-key attributes that are expected to change for the same business key across records.
- `business_key_unique_count`: optional target number of unique business-key combinations for the table (must be <= generated row count).

Validation rules:
- Static/changing columns must reference existing columns.
- Static/changing columns must not overlap.
- Business key columns cannot be listed in `business_key_changing_columns`.
- When both `business_key_changing_columns` and `scd_tracked_columns` are provided, they must match.
- `business_key_unique_count` requires `business_key` and must be a positive integer.
- For explicit row-count tables, `business_key_unique_count` must be <= `row_count`; under `scd1`, it must equal `row_count`.

## 3.3 Slowly Changing Dimension Type 1 (SCD1) (phase 1 implemented)

Definition:
- Overwrite-in-place dimension pattern linked to a business key.
- Tracked slowly-changing columns are updated on the current row only.
- No historical row versions are created.

Phase 1 schema contract (implemented):
- SCD1 links to a business key definition for the table.
- SCD1 defines which columns are "slowly changing" (`business_key_changing_columns` or legacy `scd_tracked_columns`).
- Changes to tracked columns overwrite values in the existing row for the same business key.

Rules:
- Exactly one row should exist per business key in SCD1-enabled tables.
- Duplicate rows for the same business key are invalid for SCD1.
- Active-period tracking is optional and does not imply version history when SCD1 is selected.

Future validation error examples:
- `Table 'customer_dim': SCD1 requires a business key. Fix: configure a business key before enabling SCD1.`
- `Table 'customer_dim': duplicate rows found for business key 'customer_code' under SCD1. Fix: keep one row per business key or use SCD2.`
- `Table 'customer_dim': SCD1 tracked column 'tier_old' not found. Fix: use existing column names in tracked columns.`

Implementation status:
- Runtime generation, validator enforcement, JSON IO shape, and GUI authoring controls are implemented.

## 3.4 Slowly Changing Dimension Type 2 (SCD2) (phase 1 implemented)

Definition:
- Historical versioning pattern linked to a business key.
- One business key may have multiple rows in the same table over time.
- Each version row has an active period tracked as `date` or `datetime`.

Phase 1 schema contract (implemented):
- SCD2 links to a business key definition for the table.
- SCD2 defines active-period tracking using `date` or `datetime` at table scope.
- SCD2 defines which columns are "slowly changing" (`business_key_changing_columns` or legacy `scd_tracked_columns`).
- SCD2 supports optional `business_key_static_columns` to explicitly pin stable attributes across generated versions.
- Changes to tracked columns create a new version row for the same business key.

Rules:
- Multiple rows per business key are allowed only for SCD2-enabled tables.
- Active periods must not overlap for the same business key.
- Exactly one current version should exist per business key (open-ended end time or equivalent current marker).
- All versions for the same business key must use the table's configured active-period dtype (`date` or `datetime`).

Future validation error examples:
- `Table 'customer_dim': SCD2 active period dtype must be 'date' or 'datetime'. Fix: choose one supported period dtype.`
- `Table 'customer_dim', business key 'customer_code': overlapping SCD2 active periods. Fix: ensure active periods do not overlap.`
- `Table 'customer_dim': SCD2 tracked column 'tier_old' not found. Fix: use existing column names in tracked columns.`

Implementation status:
- Runtime generation, validator enforcement, JSON IO shape, and GUI authoring controls are implemented.
- SCD2 supports both root and incoming-FK child tables; child-table version growth is bounded to FK capacity.

---

# 4. Relationships

## 4.1 Foreign Key (FK)

Definition:
- Child column references parent PK

Rules:
- Child FK column must be `dtype=int`
- Child FK column must not be child PK
- Parent column must be parent PK
- Multiple FKs per child table are allowed

Cardinality:
- `min_children`, `max_children` control child count per parent
- `min_children=0` means optional relationship (future-ready policy)

Invariants:
- FK values must exist in parent PK set
- No orphan rows unless explicitly supported by future semantics

---

# 5. Distribution Semantics

Distributions apply through generator semantics and params.

## 5.1 uniform
Valid for:
- `int`, `float|decimal`, `date`, `datetime`

## 5.2 normal
Params:
- `mean`
- `stdev` (or compatibility alias `stddev`)
- optional `decimals`, `min`, `max`
Valid for:
- `float|decimal`, `int` (rounded)
Rules:
- Standard deviation must be positive.
- Clamp to bounds when bounds exist

## 5.3 lognormal
Params:
- `median` (> 0), `sigma` (> 0)
- optional `decimals`, `min`, `max`
Valid for:
- `float|decimal`, `int` (rounded)
Rules:
- Clamp to bounds when bounds exist

## 5.4 categorical / weighted_choice
Valid for:
- `text`, `int`
Rules:
- If weights are provided, length must match choices
- If weights are provided, they must be numeric, non-negative, and include at least one value > 0

## 5.5 empirical (`sample_csv`)
Valid for:
- `text`, parseable `int`, parseable `float|decimal`
Params:
- `path` (required): CSV file path.
- `column_index` (optional, default `0`): sampled output column index.
- `match_column` (optional): source column name from the same generated row.
- `match_column_index` (required when `match_column` is set): CSV column index used to match `match_column` value.
Rules:
- Skip header row
- Deterministic selection
- Cache source content by path + column
- `params.path` may be repo-root-relative (for example `tests/fixtures/city_country_pool.csv`) or absolute; repo-root-relative references are preferred for portability.
- JSON load/save may normalize legacy absolute repo-local paths to repo-root-relative form.
- When `match_column` is set, the target column must include `match_column` in `depends_on` so source values exist before sampling.
- When `match_column` is set, only CSV rows where `match_column_index` equals the source row value are eligible for sampling.
Failure behavior:
- Missing file -> validation error
- Empty pool -> validation error
- No rows matching `match_column` source value -> validation/runtime error with fix hint

---

# 6. Correlation and Dependencies

Definition:
- Column value depends on other columns in the same row

Representation:
- `depends_on: [column_name]`

Rules:
- No circular dependencies
- Dependencies must exist in same table
- Dependent columns generate after dependencies
- Generator must not mutate unrelated columns

---

# 7. Nullability

Rules:
- PK is never nullable
- FK nullable only for optional relationship semantics
- Business key nullable only when explicitly allowed

Generator behavior:
- Default is non-null unless explicitly configured
- Optional `null_rate`/`null_probability` behavior must be deterministic

---

# 8. Validation Contract

Validation must fail fast with actionable messages containing:
- table name
- column name (when applicable)
- what is wrong
- how to fix

Example shape:
- `Table 'orders', column 'amount': min_value cannot exceed max_value. Fix: set min_value <= max_value.`

---

# 9. Invariants (Must Always Hold)

1. Exactly one PK per table
2. PK never null
3. Every FK value references a valid parent PK
4. Deterministic output for identical seed + schema
5. JSON roundtrip preserves semantics and backward-compatible float schemas
6. Values remain inside dtype domain
7. No circular dependency in `depends_on`
8. When SCD1 is enabled, exactly one row exists per business key.
9. When SCD2 is enabled, no overlapping active periods for the same business key and exactly one current version per business key.

These invariants require unit tests.

---

# 10. Extension Policy

## 10.1 Adding new data meanings

Preferred path: add or extend a generator with:
- generator name
- valid dtypes
- required params
- deterministic behavior
- tests

## 10.2 Adding new dtypes

Allowed only when representing a new storage domain not covered by:
- `int`, `float|decimal`, `text`, `bool`, `date`, `datetime`, `bytes`

Required updates:
- update this document
- define domain, constraints, export semantics
- add invariant tests
