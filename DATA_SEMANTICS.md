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

## Core design principle
**Dtypes are generic storage domains.**  
All *meaning* (email, latitude, money, status, etc.) is implemented via
**generators + params + constraints**.

All generation must remain deterministic per `project.seed`.

---

# 1. Foundational Data Types (Storage Domains)

Each `ColumnSpec` has a `dtype`. This defines its portable storage domain.
Generators may refine behavior, but must respect dtype constraints.

Supported foundational dtypes:

## 1.1 int

Definition:
- Whole number (Python `int`)
- No fractional component

Typical uses:
- Primary keys
- Foreign keys
- Counters (quantity, age, rank)
- Years

Allowed constraints:
- min_value, max_value

Rules:
- If `primary_key=true` → must be:
  - `nullable=false`
  - unique
  - deterministic

Generator behavior:
- Uniform by default unless a distribution/generator is specified
- Bounds must be enforced if provided

---

## 1.2 decimal

Definition:
- Decimal numeric domain (non-integer values)
- Implementation may be `decimal.Decimal` (preferred) or `float` (acceptable),
  but exported semantics remain decimal.

Typical uses:
- Money, measurements, rates, percentages
- Geographic coordinates (lat/lon)
- Any numeric that may contain decimals

Allowed constraints:
- min_value, max_value
- scale (optional, number of decimal places)

Generator behavior:
- Clamp to bounds if provided
- Apply scale rounding only if configured
- Deterministic per seed

---

## 1.3 text

Definition:
- Arbitrary textual value

Typical uses:
- Names, labels, categories, codes
- Emails, UUIDs, country codes (via generator semantics)
- JSON stored as text (via generator semantics)

Allowed constraints:
- min_length, max_length
- pattern (regex)
- choices (categorical)
- weights (for weighted categorical selection)
- ordered (bool, for ordered categories)

Generator behavior:
- If `choices` defined → categorical selection (uniform unless weights provided)
- If `generator="sample_csv"` → empirical sampling (cached)
- Regex constraints must be enforced

---

## 1.4 bool

Definition:
- Boolean value (`True` / `False`)

Allowed constraints:
- probability_true (0.0–1.0)

Generator behavior:
- Bernoulli distribution
- Deterministic per seed

---

## 1.5 date

Definition:
- Calendar date without time
- Stored as ISO 8601 string: `YYYY-MM-DD`

Allowed constraints:
- start_date, end_date

Generator behavior:
- Uniform random date in range unless specified otherwise
- Deterministic per seed

---

## 1.6 datetime

Definition:
- Timestamp with date + time
- Stored as ISO 8601 string
- Timezone behavior is controlled by generator semantics/params (not dtype)

Allowed constraints:
- start_datetime, end_datetime

Generator behavior:
- Uniform random within range unless specified otherwise
- Deterministic per seed

---

## 1.7 bytes

Definition:
- Binary payload (`bytes`)

Typical uses:
- Rare in CSV, but useful for DB/blob export targets

Export guidance:
- CSV exports should encode bytes (e.g., base64) at export time

Generator behavior:
- Deterministic per seed
- If a generator is used (e.g., random_bytes), it must accept length params

---

# 2. Semantic Meaning: Generators + Params

**Generators define meaning**, not dtype.

Examples:
- Email: dtype=text, generator="email", params={"domain": "example.com"}
- Latitude: dtype=decimal, generator="latitude", params={"min": -90, "max": 90}
- Status with weights: dtype=text, generator="weighted_choice", params={"choices":[...], "weights":[...]}

Rules:
- Adding a new “type of data” should normally be done by adding a generator,
  not adding a dtype.
- New dtypes should be extremely rare and must represent a new storage domain.

---

# 3. Identity Concepts

## 3.1 Primary Key (PK)

Definition:
- Surrogate identifier
- dtype=int
- primary_key=true
- nullable=false

Rules:
- Exactly one per table
- Must be unique
- Must never be null

Generator behavior:
- Sequential unless a PK generator explicitly overrides
- Deterministic for given seed
- Generated before dependent columns
- PK cannot be correlated (must not depend_on other columns)

Invariant:
- PK is never null and is unique

---

## 3.2 Business Key

Definition:
- Real-world unique identifier
- May be natural (email) or synthetic (customer_number)
- Does not replace PK

Rules:
- If a column is declared as a business key (via flag/metadata):
  - it must be unique (or composite uniqueness future)
- May be nullable only if explicitly allowed (models incomplete records)

Generator behavior:
- Must enforce uniqueness constraint
- Retry generation on collisions (with a safety limit + descriptive error)

---

# 4. Relationships

## 4.1 Foreign Key (FK)

Definition:
- References parent table primary key

Rules:
- child_column must be dtype=int
- child_column must not equal child PK
- parent_column must be parent PK
- Multiple FKs per child table are allowed

Cardinality:
- min_children, max_children control child count per parent
- min_children=0 allowed for optional relationship

Generator behavior:
- Parent tables generated first
- Child rows generated per parent cardinality
- FK values must exist in parent PK set
- No orphan rows unless explicitly allowed by a generator/param (future)

Invariant:
- FK integrity must pass in-memory test for all FK relationships

---

# 5. Distribution Semantics

Distributions apply via generator semantics or explicit distribution params.

## 5.1 uniform
Valid for:
- int, decimal, date, datetime

## 5.2 normal
Parameters:
- mean, stddev
Valid for:
- decimal, int (rounded)
Rules:
- Clamp to bounds

## 5.3 lognormal
Valid for:
- decimal, int (rounded)
Rules:
- Clamp to bounds

## 5.4 categorical / weighted_choice
Valid for:
- text, int
Rules:
- If weights supplied, they must match choices length

## 5.5 empirical (CSV sampling)
Valid for:
- text, int (if parseable), decimal (if parseable)
Rules:
- Skip header row
- Deterministic selection
- Cache file contents per path+column
Failure behavior:
- Missing file → validation error
- Empty pool → validation error

---

# 6. Correlation

Definition:
- Column value depends on other columns in same row

Representation:
- depends_on: [column_name]

Rules:
- No circular dependencies
- Dependencies must exist in the same table
- Dependent columns must be generated after dependencies

Generator behavior:
- Row context passed to generator
- Generator must not mutate other columns
- Dependency order must be respected

Example:
- total_price depends_on quantity and unit_price

---

# 7. Nullability

Definition:
- Whether a column may be None/null

Rules:
- PK never nullable
- FK nullable only if relationship optional and generator supports it
- Business keys nullable only if explicitly allowed

Generator behavior:
- Default: no nulls unless explicitly configured
- Optional: null_probability extension (future)

---

# 8. Temporal Modeling (Semantics via Generators)

These are *concepts*, not dtypes. They should be implemented as generators on
dtype=date/datetime/bool/text.

Examples:
- data_valid_from/to → dtype=date/datetime + generator="validity_range"
- is_active → dtype=bool + generator="active_flag"
- timestamps with UTC enforcement → dtype=datetime + generator="timestamp_utc"

Rules:
- End date/time must be >= start date/time
- Historical records preserved when modeling SCD (future)

---

# 9. Ordered Categories (Semantics via Constraints)

Definition:
- Categorical data with ranking

Representation:
- dtype=text
- choices=[...]
- ordered=true

Rules:
- Ordering affects progression logic only if a progression generator is used
- By default, ordered categories behave like normal categorical choices

---

# 10. Constraint Enforcement

Constraints must be enforced by either:
- validation (schema-time), or
- generator runtime checks (value-time), or both.

Rules:
- Validation errors must be actionable:
  - table name
  - column name
  - what is wrong
  - how to fix

---

# 11. Invariants (Must Always Hold)

1. Exactly one PK per table
2. PK never null
3. FK always references valid parent PK for all foreign keys
4. Deterministic output for identical seed + schema
5. JSON schema roundtrip preserves semantics
6. No column violates dtype domain (e.g., text values for int)
7. No circular dependency in depends_on graph

These invariants must have unit tests.

---

# 12. Implementation Contract

Generator functions must:
- Be deterministic given `rng` and `project.seed`
- Respect dtype constraints
- Respect nullability rules
- Raise descriptive `ValueError` for invalid params

Validation must:
- Run before generation
- Block invalid schemas
- Provide actionable error messages

---

# 13. Extension Policy

## 13.1 Adding new “data meanings”
Add a generator (preferred):
- generator name
- valid dtypes
- required params
- deterministic behavior
- tests

## 13.2 Adding new dtypes
Only allowed if representing a new storage domain not covered by:
- int, decimal, text, bool, date, datetime, bytes

New dtypes must:
- be added to this document
- define domain + constraints + export semantics
- include invariant tests
