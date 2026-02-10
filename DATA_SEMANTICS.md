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

- Runtime support today: `int`, `decimal`, legacy `float`, `text`, `bool`, `date`, `datetime`
- Canonical authoring dtypes: `int`, `decimal`, `text`, `bool`, `date`, `datetime`
- Future extension candidate: `bytes` (outside Direction 3 scope)
- Backward compatibility policy: existing JSON schemas using `float` remain supported.
- GUI authoring policy: new columns use `decimal`; GUI blocks new `float` column creation.
- SCD Type 1 and Type 2 are implemented in generator + validator + JSON IO + GUI authoring controls (business-key linkage, tracked slowly-changing columns, and SCD2 active periods).
- SCD current limitation: `scd2` is validated for root tables only (no incoming FKs) in phase 1.

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

## 1.8 bytes (future extension binary dtype)

Definition:
- Binary payload (`bytes`) for blob-like data

Rules:
- CSV exports should encode bytes (for example base64) at export time.
- Support is future roadmap-level and not part of Direction 3 completion.

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

## 3.3 Slowly Changing Dimension Type 1 (SCD1) (phase 1 implemented)

Definition:
- Overwrite-in-place dimension pattern linked to a business key.
- Tracked slowly-changing columns are updated on the current row only.
- No historical row versions are created.

Phase 1 schema contract (implemented):
- SCD1 links to a business key definition for the table.
- SCD1 defines which columns are "slowly changing" (`tracked_columns`).
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
- SCD2 defines which columns are "slowly changing" (`tracked_columns`).
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
- Phase 1 scope: `scd2` currently supports root tables only (no incoming FKs).

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
- `mean`, `stddev`
Valid for:
- `float|decimal`, `int` (rounded)
Rules:
- Clamp to bounds when bounds exist

## 5.3 lognormal
Valid for:
- `float|decimal`, `int` (rounded)
Rules:
- Clamp to bounds when bounds exist

## 5.4 categorical / weighted_choice
Valid for:
- `text`, `int`
Rules:
- If weights are provided, length must match choices

## 5.5 empirical (`sample_csv`)
Valid for:
- `text`, parseable `int`, parseable `float|decimal`
Rules:
- Skip header row
- Deterministic selection
- Cache source content by path + column
Failure behavior:
- Missing file -> validation error
- Empty pool -> validation error

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
