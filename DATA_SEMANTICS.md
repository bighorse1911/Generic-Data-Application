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

## Implementation status (2026-02-09)

Direction 3 (float -> decimal) is in progress.

- Runtime support today: `int`, `float`, `text`, `bool`, `date`, `datetime`
- Target canonical dtypes: `int`, `decimal`, `text`, `bool`, `date`, `datetime`, `bytes`
- Backward compatibility policy: existing JSON schemas using `float` remain supported
  during migration.

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

## 1.2 decimal (target canonical numeric dtype)

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

## 1.8 bytes (target canonical binary dtype)

Definition:
- Binary payload (`bytes`) for blob-like data

Rules:
- CSV exports should encode bytes (for example base64) at export time.
- Support is roadmap-level unless explicitly implemented in runtime.

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
- If marked as business key (metadata/flag), enforce uniqueness.
- Nullable only when explicitly allowed by model semantics.

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
