from __future__ import annotations

from src.gui.v2.routes import run_hooks
from src.gui.v2.routes.adapters import _BackToRouteAdapter
from src.gui.v2.routes.errors import _v2_error
from src.gui.v2.routes.home_impl import HomeV2Screen
from src.gui.v2.routes.run_center_impl import RunCenterV2Screen
from src.gui.v2.routes.schema_studio_impl import SchemaStudioV2Screen
from src.gui.v2.routes.shell_impl import V2ShellFrame
from src.gui.v2.routes.specialists_impl import ERDDesignerV2Screen
from src.gui.v2.routes.specialists_impl import GenerationBehaviorsGuideV2Screen
from src.gui.v2.routes.specialists_impl import LocationSelectorV2Screen
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui.v2.routes.theme_shared import V2_HEADER_BG
from src.gui.v2.routes.theme_shared import V2_INSPECTOR_BG
from src.gui.v2.routes.theme_shared import V2_NAV_ACTIVE
from src.gui.v2.routes.theme_shared import V2_NAV_BG
from src.gui.v2.routes.theme_shared import V2_PANEL

run_shared_estimate = run_hooks.run_shared_estimate
run_shared_build_partition_plan = run_hooks.run_shared_build_partition_plan
run_shared_benchmark = run_hooks.run_shared_benchmark
build_profile_from_model = run_hooks.build_profile_from_model
run_generation_multiprocess = run_hooks.run_generation_multiprocess
filedialog = run_hooks.filedialog

__all__ = [
    "_v2_error",
    "_BackToRouteAdapter",
    "V2_BG",
    "V2_PANEL",
    "V2_NAV_BG",
    "V2_NAV_ACTIVE",
    "V2_HEADER_BG",
    "V2_INSPECTOR_BG",
    "V2ShellFrame",
    "HomeV2Screen",
    "SchemaStudioV2Screen",
    "RunCenterV2Screen",
    "ERDDesignerV2Screen",
    "LocationSelectorV2Screen",
    "GenerationBehaviorsGuideV2Screen",
    "run_shared_estimate",
    "run_shared_build_partition_plan",
    "run_shared_benchmark",
    "build_profile_from_model",
    "run_generation_multiprocess",
    "filedialog",
]
