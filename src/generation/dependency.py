"""Public dependency ordering helpers for generation and storage layers."""

from __future__ import annotations

from src.generation.common import _runtime_error
from src.schema_project_model import SchemaProject

def _dependency_order(project: SchemaProject) -> list[str]:
    """
    Return table names in parent->child order using Kahn's algorithm.
    MVP guarantees <=1 FK per child, but algorithm works regardless.
    """
    table_names = [t.table_name for t in project.tables]
    deps = {t: set() for t in table_names}       # t depends on these
    rev = {t: set() for t in table_names}        # these depend on t

    for fk in project.foreign_keys:
        child = fk.child_table
        parent = fk.parent_table
        deps[child].add(parent)
        rev[parent].add(child)

    # Optional additional fk sort
    # fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    # for fk in project.foreign_keys:
    #     fks_by_child.setdefault(fk.child_table, []).append(fk)

    # Kahn
    ready = [t for t in table_names if len(deps[t]) == 0]
    ready.sort()
    out = []

    while ready:
        n = ready.pop(0)
        out.append(n)
        for child in sorted(rev[n]):
            deps[child].discard(n)
            if len(deps[child]) == 0:
                ready.append(child)
                ready.sort()

    if len(out) != len(table_names):
        raise ValueError(
            _runtime_error(
                "Project foreign keys",
                "cycle detected in table dependency graph",
                "remove circular foreign key dependencies",
            )
        )

    return out


def dependency_order(project: SchemaProject) -> list[str]:
    return _dependency_order(project)


__all__ = ["dependency_order", "_dependency_order"]
