"""Shared visual tokens for the v2 GUI route family."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "V2ColorRoles",
    "V2TypeScale",
    "V2SpacingScale",
    "V2FocusState",
    "V2ButtonRole",
    "V2ButtonHierarchy",
    "V2VisualTokens",
    "V2_THEME",
    "v2_button_options",
]


@dataclass(frozen=True)
class V2ColorRoles:
    app_bg: str
    panel_bg: str
    header_bg: str
    header_fg: str
    nav_bg: str
    nav_fg: str
    nav_active_bg: str
    nav_active_fg: str
    inspector_bg: str
    text_primary: str
    text_muted: str
    status_bg: str
    status_fg: str
    border_subtle: str
    focus_ring: str


@dataclass(frozen=True)
class V2TypeScale:
    display_title: tuple[str, int, str]
    page_title: tuple[str, int, str]
    section_title: tuple[str, int, str]
    body: tuple[str, int]
    body_bold: tuple[str, int, str]
    body_small: tuple[str, int]


@dataclass(frozen=True)
class V2SpacingScale:
    xxs: int
    xs: int
    sm: int
    md: int
    lg: int
    xl: int
    xxl: int


@dataclass(frozen=True)
class V2FocusState:
    ring_color: str
    ring_thickness: int


@dataclass(frozen=True)
class V2ButtonRole:
    bg: str
    fg: str
    active_bg: str
    active_fg: str
    border_color: str


@dataclass(frozen=True)
class V2ButtonHierarchy:
    primary: V2ButtonRole
    secondary: V2ButtonRole
    nav: V2ButtonRole


@dataclass(frozen=True)
class V2VisualTokens:
    colors: V2ColorRoles
    type_scale: V2TypeScale
    spacing: V2SpacingScale
    focus: V2FocusState
    buttons: V2ButtonHierarchy


V2_THEME = V2VisualTokens(
    colors=V2ColorRoles(
        app_bg="#f4efe6",
        panel_bg="#fbf8f1",
        header_bg="#0f2138",
        header_fg="#f5f5f5",
        nav_bg="#14334f",
        nav_fg="#f5f5f5",
        nav_active_bg="#c76d2a",
        nav_active_fg="#ffffff",
        inspector_bg="#e9deca",
        text_primary="#1f1f1f",
        text_muted="#333333",
        status_bg="#d7ccba",
        status_fg="#242424",
        border_subtle="#9d8d72",
        focus_ring="#1f6fb3",
    ),
    type_scale=V2TypeScale(
        display_title=("Cambria", 18, "bold"),
        page_title=("Cambria", 16, "bold"),
        section_title=("Cambria", 14, "bold"),
        body=("Calibri", 11),
        body_bold=("Calibri", 10, "bold"),
        body_small=("Calibri", 10),
    ),
    spacing=V2SpacingScale(
        xxs=2,
        xs=4,
        sm=8,
        md=10,
        lg=12,
        xl=16,
        xxl=22,
    ),
    focus=V2FocusState(
        ring_color="#1f6fb3",
        ring_thickness=2,
    ),
    buttons=V2ButtonHierarchy(
        primary=V2ButtonRole(
            bg="#c76d2a",
            fg="#ffffff",
            active_bg="#b85f20",
            active_fg="#ffffff",
            border_color="#9d8d72",
        ),
        secondary=V2ButtonRole(
            bg="#d9d2c4",
            fg="#1f1f1f",
            active_bg="#cbbfa9",
            active_fg="#1f1f1f",
            border_color="#9d8d72",
        ),
        nav=V2ButtonRole(
            bg="#14334f",
            fg="#f5f5f5",
            active_bg="#c76d2a",
            active_fg="#ffffff",
            border_color="#9d8d72",
        ),
    ),
)


def v2_button_options(role: str) -> dict[str, object]:
    key = str(role).strip().lower()
    if key == "primary":
        token = V2_THEME.buttons.primary
    elif key == "secondary":
        token = V2_THEME.buttons.secondary
    elif key == "nav":
        token = V2_THEME.buttons.nav
    else:
        raise ValueError(
            f"V2 theme tokens: unsupported button role '{role}'. "
            "Fix: use one of 'primary', 'secondary', or 'nav'."
        )
    return {
        "bg": token.bg,
        "fg": token.fg,
        "activebackground": token.active_bg,
        "activeforeground": token.active_fg,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": V2_THEME.focus.ring_thickness,
        "highlightbackground": token.border_color,
        "highlightcolor": V2_THEME.focus.ring_color,
        "takefocus": 1,
    }
