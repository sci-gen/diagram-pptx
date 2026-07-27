"""Unit-aware typography settings for slide-oriented diagram output."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

FontFit = Literal["fit", "none"]
FontUnit = Literal["pt", "px", "slide_height", "source"]

_FONT_SIZE_RE = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*"
    r"(?P<unit>pt|px|%sh|%h)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FontSize:
    """A font size with an explicit unit.

    Public sizes use points, CSS pixels (96 dpi), or a fraction of the slide
    height. ``source`` is reserved for Mermaid/SVG geometry whose text scales
    with the imported diagram.
    """

    value: float
    unit: FontUnit = "pt"

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("font size must be greater than zero")
        if self.unit not in {"pt", "px", "slide_height", "source"}:
            raise ValueError(f"Unsupported font-size unit: {self.unit!r}")
        if self.unit == "slide_height" and self.value > 1:
            raise ValueError("slide-height font sizes must be a fraction between 0 and 1")

    @classmethod
    def pt(cls, value: float) -> FontSize:
        return cls(float(value), "pt")

    @classmethod
    def px(cls, value: float) -> FontSize:
        return cls(float(value), "px")

    @classmethod
    def slide_height(cls, fraction: float) -> FontSize:
        return cls(float(fraction), "slide_height")

    @classmethod
    def source(cls, value: float) -> FontSize:
        """Create an internal source-relative size used by SVG import."""

        return cls(float(value), "source")

    @classmethod
    def parse(
        cls,
        value: FontSize | float | int | str | Mapping[str, Any],
    ) -> FontSize:
        """Parse a public size; bare numbers are points."""

        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise TypeError("font size must be numeric, a unit string, or a mapping")
        if isinstance(value, (int, float)):
            return cls.pt(float(value))
        if isinstance(value, str):
            match = _FONT_SIZE_RE.match(value)
            if not match:
                raise ValueError(
                    "font size strings must use pt, px, or %sh, for example "
                    "'12pt', '16px', or '2.2%sh'"
                )
            number = float(match.group("value"))
            unit = match.group("unit").lower()
            if unit == "pt":
                return cls.pt(number)
            if unit == "px":
                return cls.px(number)
            return cls.slide_height(number / 100.0)
        if isinstance(value, Mapping):
            unit = str(value.get("unit", "pt")).strip().lower()
            number = float(value["value"])
            aliases = {"%sh": "slide_height", "%h": "slide_height"}
            unit = aliases.get(unit, unit)
            if unit == "source":
                raise ValueError("'source' is an internal font-size unit")
            return cls(number, unit)  # type: ignore[arg-type]
        raise TypeError("font size must be numeric, a unit string, or a mapping")

    @property
    def is_absolute(self) -> bool:
        """Whether the value describes a final size on the output page."""

        return self.unit != "source"

    def resolve(self, *, slide_height_points: float = 540.0) -> float:
        """Resolve the size to PowerPoint points."""

        if slide_height_points <= 0:
            raise ValueError("slide_height_points must be greater than zero")
        if self.unit in {"pt", "source"}:
            return self.value
        if self.unit == "px":
            return self.value * 72.0 / 96.0
        return self.value * slide_height_points

    def to_json_value(self) -> float | str:
        if self.unit == "pt":
            return self.value
        if self.unit == "px":
            return f"{self.value:g}px"
        if self.unit == "slide_height":
            return f"{self.value * 100:g}%sh"
        return self.value


FontSizeInput: TypeAlias = FontSize | float | int | str | Mapping[str, Any]


def coerce_font_size(value: FontSizeInput | None) -> FontSize | None:
    return None if value is None else FontSize.parse(value)


@dataclass(slots=True)
class TypographySettings:
    """Reusable diagram-wide typography defaults.

    Role sizes are optional. When omitted, Mermaid or renderer defaults are
    used. ``fit`` is the default behavior; ``none`` keeps explicit absolute
    sizes even when text overflows its shape.
    """

    fit: FontFit = "fit"
    font_family: str | None = None
    japanese_font_family: str = "Yu Gothic"
    font_size: FontSize | float | int | str | Mapping[str, Any] | None = None
    node: FontSize | float | int | str | Mapping[str, Any] | None = None
    edge: FontSize | float | int | str | Mapping[str, Any] | None = None
    group: FontSize | float | int | str | Mapping[str, Any] | None = None
    text: FontSize | float | int | str | Mapping[str, Any] | None = None
    min_font_size: FontSize | float | int | str | Mapping[str, Any] = field(
        default_factory=lambda: FontSize.pt(9)
    )
    edge_min_font_size: FontSize | float | int | str | Mapping[str, Any] = field(
        default_factory=lambda: FontSize.pt(12)
    )
    max_font_size: FontSize | float | int | str | Mapping[str, Any] = field(
        default_factory=lambda: FontSize.pt(40)
    )

    def __post_init__(self) -> None:
        if self.fit not in {"fit", "none"}:
            raise ValueError("typography fit must be 'fit' or 'none'")
        if self.font_family is not None and not self.font_family.strip():
            raise ValueError("font_family must not be empty")
        if not self.japanese_font_family.strip():
            raise ValueError("japanese_font_family must not be empty")
        for name in (
            "font_size",
            "node",
            "edge",
            "group",
            "text",
            "min_font_size",
            "edge_min_font_size",
            "max_font_size",
        ):
            setattr(self, name, coerce_font_size(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "fit": self.fit,
            "japanese_font_family": self.japanese_font_family,
        }
        if self.font_family is not None:
            result["font_family"] = self.font_family
        for name in (
            "font_size",
            "node",
            "edge",
            "group",
            "text",
            "min_font_size",
            "edge_min_font_size",
            "max_font_size",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = value.to_json_value()
        return result

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any] | TypographySettings | None,
    ) -> TypographySettings:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return cls(**value.to_dict())
        return cls(**dict(value))


@dataclass(slots=True)
class DiagramSettings:
    """Reusable package settings for a compiler instance."""

    typography: TypographySettings = field(default_factory=TypographySettings)

    def __post_init__(self) -> None:
        self.typography = TypographySettings.from_dict(self.typography)

    def to_dict(self) -> dict[str, Any]:
        return {"typography": self.typography.to_dict()}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any] | DiagramSettings | None,
    ) -> DiagramSettings:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return cls(**value.to_dict())
        return cls(typography=TypographySettings.from_dict(value.get("typography")))
