from __future__ import annotations

from src.schema.types import SchemaProject
from src.schema.validators import scd
from src.schema.validators.correlation import _validate_correlation_groups_for_table
from src.schema.validators.generator_param_parsing import _parse_float_param
from src.schema.validators.generator_param_parsing import _parse_int_param
from src.schema.validators.generator_rules_dependency import validate_dependency_generator_rules
from src.schema.validators.generator_rules_numeric import validate_numeric_generator_rules
from src.schema.validators.project_table_rules import validate_column_structural_rules
from src.schema.validators.project_table_rules import validate_project_header_and_table_map
from src.schema.validators.project_table_rules import validate_table_structure
from src.schema.validators.state_transition import validate_state_transition_generator


def validate_core_project_and_table_rules(project: SchemaProject) -> dict[str, object]:
    table_map = validate_project_header_and_table_map(project)

    # Per-table validations
    for table in project.tables:
        # # We now allow for auto-sizing of children
        # if table.row_count <= 0:
        #     raise ValueError(f"Table '{table.table_name}': row_count must be > 0.")
        col_map = validate_table_structure(table)

        for column in table.columns:
            validate_column_structural_rules(table, column)
            validate_numeric_generator_rules(
                table,
                column,
                parse_float_param=_parse_float_param,
                parse_int_param=_parse_int_param,
            )
            validate_state_transition_generator(table, column, col_map)
            validate_dependency_generator_rules(table, column, col_map=col_map)

        incoming = [fk for fk in project.foreign_keys if fk.child_table == table.table_name]
        incoming_fk_cols = {fk.child_column for fk in incoming}
        _validate_correlation_groups_for_table(
            table,
            col_map=col_map,
            incoming_fk_cols=incoming_fk_cols,
        )

        scd.validate_table_scd_and_business_key(
            table,
            col_map=col_map,
            incoming_fk_cols=incoming_fk_cols,
        )

    return table_map


__all__ = ["validate_core_project_and_table_rules"]
