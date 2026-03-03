"""Compatibility shim for v2 redesign routes.

Canonical implementations now live under `src.gui.v2.routes`.
"""

from src.gui.v2.routes import _route_impl as _route_impl
from src.gui.v2.routes import run_hooks as _run_hooks
from src.gui.v2.routes._route_impl import _BackToRouteAdapter
from src.gui.v2.routes.erd_designer import ERDDesignerV2Screen
from src.gui.v2.routes.generation_guide import GenerationBehaviorsGuideV2Screen
from src.gui.v2.routes.home import HomeV2Screen
from src.gui.v2.routes.location_selector import LocationSelectorV2Screen
from src.gui.v2.routes.run_center import RunCenterV2Screen
from src.gui.v2.routes.schema_studio import SchemaStudioV2Screen
from src.gui.v2.routes.shell import V2ShellFrame

# Keep helper symbols patchable at this legacy shim module path.
run_shared_estimate = _run_hooks.run_shared_estimate
run_shared_build_partition_plan = _run_hooks.run_shared_build_partition_plan
run_shared_benchmark = _run_hooks.run_shared_benchmark
build_profile_from_model = _run_hooks.build_profile_from_model
run_generation_multiprocess = _run_hooks.run_generation_multiprocess
filedialog = _run_hooks.filedialog

# Bridge hook callables to this shim's symbols so legacy patch targets
# (`src.gui_v2_redesign.*`) continue to affect runtime behavior.
_run_hooks.run_shared_estimate = lambda *args, **kwargs: run_shared_estimate(*args, **kwargs)
_run_hooks.run_shared_build_partition_plan = (
    lambda *args, **kwargs: run_shared_build_partition_plan(*args, **kwargs)
)
_run_hooks.run_shared_benchmark = lambda *args, **kwargs: run_shared_benchmark(*args, **kwargs)
_run_hooks.build_profile_from_model = lambda *args, **kwargs: build_profile_from_model(*args, **kwargs)
_run_hooks.run_generation_multiprocess = lambda *args, **kwargs: run_generation_multiprocess(*args, **kwargs)

# Preserve route-impl compatibility exports.
_route_impl.run_shared_estimate = _run_hooks.run_shared_estimate
_route_impl.run_shared_build_partition_plan = _run_hooks.run_shared_build_partition_plan
_route_impl.run_shared_benchmark = _run_hooks.run_shared_benchmark
_route_impl.build_profile_from_model = _run_hooks.build_profile_from_model
_route_impl.run_generation_multiprocess = _run_hooks.run_generation_multiprocess
_route_impl.filedialog = filedialog

__all__ = [
    "_BackToRouteAdapter",
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
