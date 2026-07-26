"""Renderer-neutral style, theme, and color-map primitives."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from colorsys import hls_to_rgb
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

SourceStylePolicy = Literal["merge", "preserve", "replace"]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RE = re.compile(
    r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})"
    r"(?:\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?))?\s*\)$",
    re.IGNORECASE,
)
_HSL_RE = re.compile(
    r"^hsla?\(\s*(-?(?:\d+(?:\.\d*)?|\.\d+))(?:deg)?\s*,\s*"
    r"(\d+(?:\.\d*)?)%\s*,\s*(\d+(?:\.\d*)?)%"
    r"(?:\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?))?\s*\)$",
    re.IGNORECASE,
)
THEME_COLOR_NAMES = {
    "background1",
    "text1",
    "background2",
    "text2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hyperlink",
    "followed_hyperlink",
}
_CSS_COLORS = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "gray": "#808080",
    "grey": "#808080",
    "lightgray": "#D3D3D3",
    "lightgrey": "#D3D3D3",
    "darkgray": "#A9A9A9",
    "darkgrey": "#A9A9A9",
    "orange": "#FFA500",
    "purple": "#800080",
    "transparent": "#00000000",
}

_CONTINUOUS_COLOR_MAPS: dict[str, tuple[tuple[float, str], ...]] = {
    "jet": (
        (0.00, "#00007F"),
        (0.12, "#0000FF"),
        (0.38, "#00FFFF"),
        (0.62, "#FFFF00"),
        (0.88, "#FF0000"),
        (1.00, "#7F0000"),
    ),
    "viridis": (
        (0.00, "#440154"),
        (0.25, "#3B528B"),
        (0.50, "#21918C"),
        (0.75, "#5EC962"),
        (1.00, "#FDE725"),
    ),
    "plasma": (
        (0.00, "#0D0887"),
        (0.25, "#7E03A8"),
        (0.50, "#CC4778"),
        (0.75, "#F89540"),
        (1.00, "#F0F921"),
    ),
    "magma": (
        (0.00, "#000004"),
        (0.25, "#51127C"),
        (0.50, "#B73779"),
        (0.75, "#FC8961"),
        (1.00, "#FCFDBF"),
    ),
}


def normalize_color(value: str) -> str:
    """Normalize common CSS color notations while preserving theme/token names."""

    text = re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.IGNORECASE)
    lower = text.lower()
    if lower in _CSS_COLORS:
        return _CSS_COLORS[lower]
    match = _HEX_RE.match(text)
    if match:
        digits = match.group(1).upper()
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        return f"#{digits}"
    rgb = _RGB_RE.match(text)
    if rgb:
        red, green, blue = (max(0, min(255, int(rgb.group(i)))) for i in range(1, 4))
        alpha = rgb.group(4)
        if alpha is None:
            return f"#{red:02X}{green:02X}{blue:02X}"
        alpha_byte = round(float(alpha) * 255)
        return f"#{red:02X}{green:02X}{blue:02X}{alpha_byte:02X}"
    hsl = _HSL_RE.match(text)
    if hsl:
        hue = float(hsl.group(1)) % 360 / 360
        saturation = max(0.0, min(100.0, float(hsl.group(2)))) / 100
        lightness = max(0.0, min(100.0, float(hsl.group(3)))) / 100
        red_float, green_float, blue_float = hls_to_rgb(
            hue,
            lightness,
            saturation,
        )
        red, green, blue = (
            round(channel * 255) for channel in (red_float, green_float, blue_float)
        )
        alpha = hsl.group(4)
        if alpha is None:
            return f"#{red:02X}{green:02X}{blue:02X}"
        alpha_byte = round(float(alpha) * 255)
        return f"#{red:02X}{green:02X}{blue:02X}{alpha_byte:02X}"
    return lower if lower in THEME_COLOR_NAMES else text


def sample_colormap(name: str, position: float) -> str:
    """Sample a named continuous color map at a position from 0 through 1."""

    normalized_name = name.strip().lower()
    if normalized_name not in _CONTINUOUS_COLOR_MAPS:
        supported = ", ".join(sorted(_CONTINUOUS_COLOR_MAPS))
        raise ValueError(f"Unknown colormap {name!r}; choose one of: {supported}")
    if not 0.0 <= position <= 1.0:
        raise ValueError(f"Colormap position must be between 0 and 1, got {position}")
    stops = _CONTINUOUS_COLOR_MAPS[normalized_name]
    for index, (stop, color) in enumerate(stops):
        if position == stop or index == len(stops) - 1:
            return color
        next_stop, next_color = stops[index + 1]
        if stop <= position <= next_stop:
            ratio = (position - stop) / (next_stop - stop)
            start_rgb = tuple(int(color[offset : offset + 2], 16) for offset in (1, 3, 5))
            end_rgb = tuple(int(next_color[offset : offset + 2], 16) for offset in (1, 3, 5))
            channels = tuple(
                round(start + (end - start) * ratio)
                for start, end in zip(start_rgb, end_rgb, strict=True)
            )
            return f"#{channels[0]:02X}{channels[1]:02X}{channels[2]:02X}"
    return stops[-1][1]


@dataclass(frozen=True, slots=True)
class ColorMapStyle:
    """Map visual channels to positions in a continuous color map.

    Args:
        name: One of ``jet``, ``viridis``, ``plasma``, or ``magma``.
        primary: Shorthand position for ordinary node fills.
        secondary: Shorthand position for decision fills, outlines,
            connectors, and container lines.
        fill: Ordinary node fill position.
        line: Node outline position.
        text: Explicit text position. When omitted, filled nodes choose
            contrasting light or dark text automatically.
        edge: Connector line position.
        decision_fill: Decision-node fill position.
        group_line: Container outline position.
        label_fill: Connector-label background position.

    Every position is a float from ``0`` through ``1``. Explicit channel
    values override the ``primary`` and ``secondary`` shorthand.
    """

    name: str
    primary: float | None = None
    secondary: float | None = None
    fill: float | None = None
    line: float | None = None
    text: float | None = None
    edge: float | None = None
    decision_fill: float | None = None
    group_line: float | None = None
    label_fill: float | None = None

    def __post_init__(self) -> None:
        # Validate the name and every explicitly configured channel.
        sample_colormap(self.name, 0.0)
        for property_name in (
            "primary",
            "secondary",
            "fill",
            "line",
            "text",
            "edge",
            "decision_fill",
            "group_line",
            "label_fill",
        ):
            value = getattr(self, property_name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{property_name} colormap position must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping without unset channels."""

        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if getattr(self, item.name) is not None
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any] | ColorMapStyle,
    ) -> ColorMapStyle:
        """Create validated color-map settings from a JSON-like mapping."""

        if isinstance(value, cls):
            return value
        allowed = {item.name for item in fields(cls)}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown color-map properties: {', '.join(sorted(unknown))}")
        if not value.get("name"):
            raise ValueError("Color-map settings require a name")
        return cls(**dict(value))

    def color(self, channel: str) -> str | None:
        position = self.position(channel)
        return None if position is None else sample_colormap(self.name, position)

    def position(self, channel: str) -> float | None:
        explicit = getattr(self, channel)
        if explicit is not None:
            return explicit
        if channel == "fill":
            return self.primary if self.primary is not None else 0.82
        if channel in {"line", "edge", "decision_fill", "group_line"}:
            if self.secondary is not None:
                return self.secondary
            return {
                "line": 0.25,
                "edge": 0.35,
                "decision_fill": 0.96,
                "group_line": 0.25,
            }[channel]
        return None


def contrast_text_color(
    background: str,
    *,
    light: str = "#FFFFFF",
    dark: str = "#111827",
) -> str:
    """Choose the higher-contrast light or dark text color for a background."""

    background_luminance = _relative_luminance(background)
    light_luminance = _relative_luminance(light)
    dark_luminance = _relative_luminance(dark)
    light_ratio = (max(background_luminance, light_luminance) + 0.05) / (
        min(background_luminance, light_luminance) + 0.05
    )
    dark_ratio = (max(background_luminance, dark_luminance) + 0.05) / (
        min(background_luminance, dark_luminance) + 0.05
    )
    return normalize_color(light if light_ratio >= dark_ratio else dark)


def _relative_luminance(color: str) -> float:
    normalized = normalize_color(color)
    if not normalized.startswith("#") or len(normalized) not in {7, 9}:
        raise ValueError(f"Contrast calculation requires an RGB/RGBA color, got {color!r}")
    channels = [int(normalized[offset : offset + 2], 16) / 255 for offset in (1, 3, 5)]

    def linearize(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearize(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


@dataclass(slots=True)
class ElementStyle:
    """Typed visual properties shared by semantic and drawing elements.

    Colors accept RGB/RGBA strings, CSS color forms, palette tokens, and
    PowerPoint theme slots such as ``accent1`` or ``text1``. Unset properties
    remain ``None`` so style layers can be merged predictably.
    """

    fill: str | None = None
    line: str | None = None
    text: str | None = None
    line_width: float | None = None
    dash: str | None = None
    font_family: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    opacity: float | None = None
    label_fill: str | None = None

    def copy(self) -> ElementStyle:
        return ElementStyle(**self.to_dict())

    def merged(self, *overrides: ElementStyle | None) -> ElementStyle:
        values = self.to_dict()
        for override in overrides:
            if override is None:
                continue
            values.update(
                {
                    item.name: getattr(override, item.name)
                    for item in fields(ElementStyle)
                    if getattr(override, item.name) is not None
                }
            )
        return ElementStyle(**values)

    def to_dict(self) -> dict[str, Any]:
        return {
            item.name: getattr(self, item.name)
            for item in fields(ElementStyle)
            if getattr(self, item.name) is not None
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | ElementStyle | None) -> ElementStyle:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.copy()
        allowed = {item.name for item in fields(cls)}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown style properties: {', '.join(sorted(unknown))}")
        return cls(**dict(value))

    # Keep the old mapping-style access convenient during the alpha transition.
    def get(self, key: str, default: Any = None) -> Any:
        value = getattr(self, key, None)
        return default if value is None else value

    def update(self, other: Mapping[str, Any] | ElementStyle) -> None:
        incoming = ElementStyle.from_dict(other)
        for item in fields(ElementStyle):
            value = getattr(incoming, item.name)
            if value is not None:
                setattr(self, item.name, value)

    def __getitem__(self, key: str) -> Any:
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return value


@dataclass(slots=True)
class DiagramTheme:
    """Named colors and semantic style rules for every diagram family.

    ``roles`` defines semantic defaults, ``classes`` applies Mermaid class
    rules, ``ids`` targets individual elements, and ``color_map`` performs the
    final exact-color replacement. Themes round-trip through versioned JSON.
    """

    schema_version: int = 1
    palette: dict[str, str] = field(default_factory=dict)
    roles: dict[str, ElementStyle] = field(default_factory=dict)
    classes: dict[str, ElementStyle] = field(default_factory=dict)
    ids: dict[str, ElementStyle] = field(default_factory=dict)
    color_map: dict[str, str] = field(default_factory=dict)
    defaults: ElementStyle = field(default_factory=ElementStyle)

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported theme schema_version: {self.schema_version}")
        self.palette = {name: normalize_color(value) for name, value in self.palette.items()}
        self.roles = {name: ElementStyle.from_dict(style) for name, style in self.roles.items()}
        self.classes = {name: ElementStyle.from_dict(style) for name, style in self.classes.items()}
        self.ids = {name: ElementStyle.from_dict(style) for name, style in self.ids.items()}
        self.color_map = {
            normalize_color(source): normalize_color(target)
            for source, target in self.color_map.items()
        }
        self.defaults = ElementStyle.from_dict(self.defaults)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "palette": dict(self.palette),
            "defaults": self.defaults.to_dict(),
            "roles": {name: style.to_dict() for name, style in self.roles.items()},
            "classes": {name: style.to_dict() for name, style in self.classes.items()},
            "ids": {name: style.to_dict() for name, style in self.ids.items()},
            "color_map": dict(self.color_map),
        }

    def merged(self, override: DiagramTheme | Mapping[str, Any] | None) -> DiagramTheme:
        other = DiagramTheme.from_dict(override)
        roles = dict(self.roles)
        for name, style in other.roles.items():
            roles[name] = roles.get(name, ElementStyle()).merged(style)
        classes = dict(self.classes)
        for name, style in other.classes.items():
            classes[name] = classes.get(name, ElementStyle()).merged(style)
        ids = dict(self.ids)
        for name, style in other.ids.items():
            ids[name] = ids.get(name, ElementStyle()).merged(style)
        return DiagramTheme(
            palette={**self.palette, **other.palette},
            defaults=self.defaults.merged(other.defaults),
            roles=roles,
            classes=classes,
            ids=ids,
            color_map={**self.color_map, **other.color_map},
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | DiagramTheme | None) -> DiagramTheme:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return cls(**value.to_dict())
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            palette=dict(value.get("palette", {})),
            defaults=ElementStyle.from_dict(value.get("defaults")),
            roles=dict(value.get("roles", {})),
            classes=dict(value.get("classes", {})),
            ids=dict(value.get("ids", {})),
            color_map=dict(value.get("color_map", {})),
        )

    @classmethod
    def from_json(cls, source: str | bytes | Path) -> DiagramTheme:
        if isinstance(source, Path):
            data = json.loads(source.read_text(encoding="utf-8"))
        elif isinstance(source, bytes):
            data = json.loads(source.decode("utf-8"))
        else:
            candidate = Path(source)
            try:
                is_file = candidate.is_file()
            except OSError:
                is_file = False
            data = (
                json.loads(candidate.read_text(encoding="utf-8")) if is_file else json.loads(source)
            )
        if not isinstance(data, dict):
            raise ValueError("Theme JSON root must be an object")
        return cls.from_dict(data)


class StyleResolver:
    """Resolve defaults, source styles, theme rules, overrides, and color maps."""

    def __init__(
        self,
        theme: DiagramTheme | Mapping[str, Any] | None = None,
        *,
        source_style: SourceStylePolicy = "merge",
    ) -> None:
        if source_style not in {"merge", "preserve", "replace"}:
            raise ValueError(f"Unsupported source_style policy: {source_style!r}")
        self.theme = DiagramTheme.from_dict(theme)
        self.source_style = source_style

    def resolve(
        self,
        *,
        element_id: str,
        role: str,
        classes: Iterable[str] = (),
        source: ElementStyle | Mapping[str, Any] | None = None,
        default: ElementStyle | Mapping[str, Any] | None = None,
        override: ElementStyle | Mapping[str, Any] | None = None,
    ) -> ElementStyle:
        base = ElementStyle.from_dict(default).merged(self.theme.defaults)
        role_style = self.theme.roles.get(role)
        source_style = ElementStyle.from_dict(source)
        class_styles = [
            self.theme.classes[name] for name in sorted(classes) if name in self.theme.classes
        ]
        id_style = self.theme.ids.get(element_id)
        final_override = ElementStyle.from_dict(override)

        if self.source_style == "replace":
            resolved = base.merged(role_style, *class_styles, id_style, final_override)
        elif self.source_style == "preserve":
            resolved = base.merged(
                role_style, *class_styles, id_style, final_override, source_style
            )
        else:
            resolved = base.merged(
                role_style, source_style, *class_styles, id_style, final_override
            )
        return self._resolve_colors(resolved)

    def _resolve_colors(self, style: ElementStyle) -> ElementStyle:
        resolved = style.copy()
        for property_name in ("fill", "line", "text", "label_fill"):
            value = getattr(resolved, property_name)
            if value is None:
                continue
            color = self._resolve_color(value, seen=set())
            mapped = self.theme.color_map.get(normalize_color(color))
            setattr(
                resolved,
                property_name,
                self._resolve_color(mapped, seen=set()) if mapped is not None else color,
            )
        return resolved

    def _resolve_color(self, value: str, *, seen: set[str]) -> str:
        normalized = normalize_color(value)
        if normalized in THEME_COLOR_NAMES or normalized.startswith("#"):
            return normalized
        if normalized in seen:
            raise ValueError(f"Palette cycle detected at {normalized!r}")
        if normalized not in self.theme.palette:
            return normalized
        seen.add(normalized)
        return self._resolve_color(self.theme.palette[normalized], seen=seen)


DEFAULT_THEME = DiagramTheme(
    palette={
        "node_fill": "#EAF2FF",
        "node_line": "#3167A5",
        "node_text": "#16324F",
        "edge": "#536273",
        "surface": "#FFFFFF",
        "group_line": "#8FA4B8",
        "group_text": "#52687A",
        "lifeline": "#A7B0BA",
    },
    roles={
        "node.default": ElementStyle(
            fill="node_fill", line="node_line", text="node_text", line_width=1.4
        ),
        "node.decision": ElementStyle(
            fill="#FFF3CD", line="#B7791F", text="#5F3B00", line_width=1.4
        ),
        "edge.default": ElementStyle(line="edge", line_width=1.4),
        "edge.label": ElementStyle(fill="surface", text="edge"),
        "group.default": ElementStyle(line="group_line", text="group_text", dash="dash"),
        "text.default": ElementStyle(text="node_text"),
        "sequence.lifeline": ElementStyle(line="lifeline", line_width=0.8, dash="dash"),
        "sequence.fragment.separator": ElementStyle(line="group_line", dash="dash"),
        "state.start": ElementStyle(fill="edge", line="edge"),
        "state.end": ElementStyle(fill="surface", line="edge"),
        "state.end.inner": ElementStyle(fill="edge", line="edge"),
    },
)

OFFICIAL_STYLE_THEME = DiagramTheme(
    palette={
        "node_fill": "#ECECFF",
        "node_line": "#9370DB",
        "node_text": "#1F2D4D",
        "edge": "#333333",
        "group_line": "#9370DB",
        "group_text": "#1F2D4D",
        "lifeline": "#9370DB",
    },
    roles={
        "node.decision": ElementStyle(
            fill="node_fill",
            line="node_line",
            text="node_text",
            line_width=1.4,
        ),
        "sequence.fragment.alt": ElementStyle(
            line="group_line",
            text="group_text",
            dash="solid",
            line_width=1.2,
        ),
    },
)


def style_preset(name: str | None) -> DiagramTheme:
    """Return a built-in visual preset without selecting a layout backend."""

    normalized = (name or "native").strip().lower()
    if normalized in {"native", "default"}:
        return DiagramTheme()
    if normalized == "official":
        return DiagramTheme.from_dict(OFFICIAL_STYLE_THEME)
    raise ValueError(f"Unknown style preset {name!r}; choose native or official")
