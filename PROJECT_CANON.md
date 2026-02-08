# Generic Data Application — Project Canon

## Purpose
A GUI-driven synthetic data generator capable of producing realistic,
relational, schema-driven datasets for analytics, testing, and demos.

## Core Capabilities
- Multi-table schemas
- Multiple foreign keys per table
- Deterministic generation via seed
- CSV, SQLite output
- GUI schema designer

## Architecture
- Tkinter GUI
- Pure-Python backend (no external deps)
- Schema-first design
- Generator registry pattern

## Data Generation
- ColumnSpec drives generation
- Generators selected by dtype / generator_id
- Supports:
  - CSV sampling
  - Distributions (uniform, normal, lognormal)
  - Dates, timestamps, lat/long
  - Correlated columns via depends_on
- FK integrity enforced in-memory

## Validation
- validate_project() blocks invalid schemas
- FK integrity tests
- Defensive PK checks

## UX Principles
- Scrollable canvas
- Per-panel collapse
- No data loss on slow machines

## Non-Goals (for now)
- No external libraries
- No cloud deployment
