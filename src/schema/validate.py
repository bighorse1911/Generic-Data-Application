"""Schema validation orchestration exports."""

from src.schema.validators.correlation import correlation_cholesky_lower
from src.schema.validators.fk import validate_foreign_keys
from src.schema.validators.generators import validate_core_project_and_table_rules
from src.schema.validators.locale import validate_locale_identity_bundles
from src.schema.validators.quality_profile_fit import validate_data_quality_profiles
from src.schema.validators.quality_profile_fit import validate_sample_profile_fits
from src.schema.validators.timeline import validate_timeline_constraints


def validate_project(project) -> None:
    table_map = validate_core_project_and_table_rules(project)
    validate_foreign_keys(project, table_map=table_map)
    validate_timeline_constraints(project, table_map=table_map)
    validate_data_quality_profiles(project, table_map=table_map)
    validate_locale_identity_bundles(project, table_map=table_map)
    validate_sample_profile_fits(project, table_map=table_map)


__all__ = ["correlation_cholesky_lower", "validate_project"]
