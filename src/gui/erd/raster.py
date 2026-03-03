from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable

from src.gui.erd.common import _erd_error

FinderFn = Callable[[], str | None]
ExportRasterFn = Callable[..., None]


def _find_ghostscript_executable_impl() -> str | None:
    candidates = [
        "gswin64c",
        "gswin32c",
        "gs",
    ]
    for name in candidates:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    common_roots = [
        Path("C:/Program Files/gs"),
        Path("C:/Program Files (x86)/gs"),
    ]
    for root in common_roots:
        if not root.exists():
            continue
        for version_dir in sorted(root.glob("*"), reverse=True):
            candidate = version_dir / "bin" / "gswin64c.exe"
            if candidate.exists():
                return str(candidate)
            candidate = version_dir / "bin" / "gswin32c.exe"
            if candidate.exists():
                return str(candidate)
    return None


def _export_raster_with_ghostscript_impl(
    *,
    output_path: Path,
    postscript_data: str,
    raster_format: str,
    finder: FinderFn | None = None,
) -> None:
    gs_finder = finder if finder is not None else _find_ghostscript_executable_impl
    gs = gs_finder()
    if gs is None:
        raise ValueError(
            _erd_error(
                "Export",
                f"{raster_format.upper()} export requires Ghostscript but it was not found",
                "install Ghostscript (gswin64c) or export as SVG",
            )
        )

    device = "pngalpha" if raster_format == "png" else "jpeg"
    with tempfile.NamedTemporaryFile(suffix=".ps", delete=False) as tmp:
        ps_path = Path(tmp.name)
        tmp.write(postscript_data.encode("utf-8"))

    cmd = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        f"-sDEVICE={device}",
        "-r160",
        f"-sOutputFile={output_path}",
        str(ps_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    finally:
        try:
            ps_path.unlink()
        except OSError:
            pass

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        details = stderr.splitlines()[0] if stderr else f"ghostscript exit code {proc.returncode}"
        raise ValueError(
            _erd_error(
                "Export",
                f"failed to export {raster_format.upper()} ({details})",
                "verify Ghostscript is installed and retry, or export as SVG",
            )
        )


def export_erd_file_impl(
    *,
    output_path_value: Any,
    svg_text: str,
    postscript_data: str | None = None,
    export_raster: ExportRasterFn | None = None,
) -> Path:
    if not isinstance(output_path_value, str) or output_path_value.strip() == "":
        raise ValueError(
            _erd_error(
                "Export path",
                "output path is required",
                "choose a file path ending in .svg, .png, .jpg, or .jpeg",
            )
        )
    output_path = Path(output_path_value.strip())
    ext = output_path.suffix.lower()
    if ext not in {".svg", ".png", ".jpg", ".jpeg"}:
        raise ValueError(
            _erd_error(
                "Export format",
                f"unsupported extension '{ext or '<none>'}'",
                "use .svg, .png, .jpg, or .jpeg",
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext == ".svg":
        output_path.write_text(svg_text, encoding="utf-8")
        return output_path

    if postscript_data is None or postscript_data.strip() == "":
        raise ValueError(
            _erd_error(
                "Export source",
                f"{ext[1:].upper()} export requires rendered canvas postscript data",
                "render the ERD before exporting",
            )
        )

    raster_export = export_raster if export_raster is not None else _export_raster_with_ghostscript_impl
    raster_export(
        output_path=output_path,
        postscript_data=postscript_data,
        raster_format="png" if ext == ".png" else "jpeg",
    )
    return output_path
