from __future__ import annotations

from dataclasses import dataclass, field

from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.run_models import coerce_execution_mode
from src.gui_kit.run_models import coerce_output_mode


@dataclass
class SchemaStudioViewModel:
    """UI state for schema_studio_v2 navigation shell."""

    selected_section: str = "project"
    status_text: str = "Schema Studio v2 ready."
    inspector_title: str = "Project Inspector"
    inspector_lines: list[str] = field(default_factory=list)


class RunCenterViewModel(RunWorkflowViewModel):
    """Compatibility alias for run-center model now shared under gui_kit."""


@dataclass
class GenerationGuideV2ViewModel:
    """UI state for generation_behaviors_guide_v2."""

    selected_section: str = "guide"
    status_text: str = "Generation Guide v2 ready."


@dataclass
class LocationSelectorV2ViewModel:
    """UI state for location_selector_v2."""

    selected_section: str = "location"
    status_text: str = "Location Selector v2 ready."


@dataclass
class ERDDesignerV2ViewModel:
    """UI state for erd_designer_v2."""

    selected_section: str = "erd"
    status_text: str = "ERD Designer v2 ready."
