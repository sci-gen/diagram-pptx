"""Build public, fictional README screenshots with diagram-pptx itself."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

from diagram_pptx import parse_mermaid

ORDER_FLOW = """\
flowchart LR
    customer([Customer]) --> cart[Shopping cart]
    cart --> payment{Payment approved?}
    payment -->|retry| retry[Choose another method]
    retry --> payment
    payment -->|approved| reserve[Reserve inventory]
    reserve --> stock{Items available?}
    stock -->|no| refund[Issue refund]
    stock -->|yes| pack[Pack order]
    pack --> ship[Ship parcel]
    ship --> notify[Send tracking]
    notify --> delivered([Delivered])
"""

CHECKOUT_SEQUENCE = """\
sequenceDiagram
    autonumber
    actor C as Customer
    participant S as Storefront
    participant P as Payment
    participant I as Inventory
    participant D as Delivery

    C->>S: Place order
    S->>P: Authorize payment

    alt Payment approved
        P-->>S: Authorization confirmed
        S->>I: Reserve items
        I-->>S: Reservation confirmed
        S->>D: Create shipment
        D-->>S: Tracking number
        S-->>C: Order confirmed
    else Payment declined
        P-->>S: Authorization declined
        S-->>C: Retry payment
    end
"""

HERO_DIAGRAMS = (
    """\
flowchart TD
    idea([Idea]) --> review{Ready?}
    review -->|yes| ship([Ship])
    review -->|no| refine[Refine]
""",
    """\
sequenceDiagram
    actor U as User
    participant A as API
    participant D as Data
    U->>A: Request
    A->>D: Query
    D-->>A: Result
    A-->>U: Response
""",
    """\
classDiagram
    direction TB
    class Service {
        +run()
    }
    class Store {
        +save()
    }
    Service --> Store : uses
""",
    """\
stateDiagram-v2
    [*] --> Draft
    Draft --> Review : submit
    Review --> Published : approve
    Published --> [*]
""",
)

HERO_PALETTES = (
    {
        "node_fill": "#DCFCE7",
        "node_line": "#16A34A",
        "node_text": "#14532D",
        "decision_fill": "#0F766E",
        "decision_line": "#115E59",
        "edge": "#3F6F63",
        "surface": "#F8FAFC",
        "muted": "#8AAE9F",
    },
    {
        "node_fill": "#DBEAFE",
        "node_line": "#2563EB",
        "node_text": "#1E3A8A",
        "decision_fill": "#1D4ED8",
        "decision_line": "#1E40AF",
        "edge": "#49698D",
        "surface": "#F8FAFC",
        "muted": "#94A3B8",
    },
    {
        "node_fill": "#FFEDD5",
        "node_line": "#EA580C",
        "node_text": "#7C2D12",
        "decision_fill": "#C2410C",
        "decision_line": "#9A3412",
        "edge": "#8C5B3E",
        "surface": "#F8FAFC",
        "muted": "#B7A08E",
    },
    {
        "node_fill": "#EDE9FE",
        "node_line": "#7C3AED",
        "node_text": "#4C1D95",
        "decision_fill": "#6D28D9",
        "decision_line": "#5B21B6",
        "edge": "#66558A",
        "surface": "#F8FAFC",
        "muted": "#A69BC0",
    },
)

BASE_THEME = {
    "defaults": {"font_family": "Noto Sans CJK JP"},
    "roles": {
        "node.default": {
            "fill": "#EFF6FF",
            "line": "#2563EB",
            "text": "#0F172A",
            "line_width": 1.5,
        },
        "node.decision": {
            "fill": "#0F766E",
            "line": "#115E59",
            "text": "#FFFFFF",
            "line_width": 1.7,
        },
        "edge.default": {
            "line": "#475569",
            "text": "#334155",
            "label_fill": "#F8FAFC",
            "line_width": 1.35,
        },
        "group.default": {
            "line": "#94A3B8",
            "text": "#334155",
        },
    },
    "ids": {
        "refund": {"fill": "#FEF2F2", "line": "#DC2626", "text": "#7F1D1D"},
        "retry": {"fill": "#FFF7ED", "line": "#EA580C", "text": "#7C2D12"},
        "delivered": {"fill": "#ECFDF5", "line": "#16A34A", "text": "#14532D"},
    },
}


def _hero_theme(palette: dict[str, str]) -> dict[str, object]:
    return {
        "defaults": {"font_family": "Noto Sans CJK JP", "font_size": 15},
        "palette": palette,
        "roles": {
            "node.default": {
                "fill": "node_fill",
                "line": "node_line",
                "text": "node_text",
                "line_width": 1.7,
            },
            "node.decision": {
                "fill": "decision_fill",
                "line": "decision_line",
                "text": "#FFFFFF",
                "line_width": 1.8,
            },
            "edge.default": {
                "line": "edge",
                "text": "edge",
                "line_width": 1.45,
            },
            "edge.label": {"fill": "surface", "text": "edge"},
            "group.default": {"line": "muted", "text": "node_text"},
            "sequence.lifeline": {
                "line": "muted",
                "line_width": 0.9,
                "dash": "dash",
            },
            "state.start": {"fill": "edge", "line": "edge"},
            "state.end": {"fill": "surface", "line": "edge"},
            "state.end.inner": {"fill": "edge", "line": "edge"},
        },
    }


def _build_hero(path: Path) -> None:
    canvas_width = 2400
    canvas_height = 660
    horizontal_margin = 55
    vertical_margin = 42
    gap = 34
    panel_width = (canvas_width - horizontal_margin * 2 - gap * (len(HERO_DIAGRAMS) - 1)) // len(
        HERO_DIAGRAMS
    )
    panel_height = canvas_height - vertical_margin * 2
    canvas = Image.new("RGB", (canvas_width, canvas_height), "#F8FAFC")

    for index, (source, palette) in enumerate(zip(HERO_DIAGRAMS, HERO_PALETTES, strict=True)):
        document = parse_mermaid(source, strict=True)
        png = document.to_png(
            width_px=900,
            background="transparent",
            label_background="#F8FAFC",
            style="official",
            theme=_hero_theme(palette),
        )
        diagram = Image.open(BytesIO(png)).convert("RGBA")
        diagram.thumbnail((panel_width, panel_height), Image.Resampling.LANCZOS)

        panel_left = horizontal_margin + index * (panel_width + gap)
        left = panel_left + (panel_width - diagram.width) // 2
        top = vertical_margin + (panel_height - diagram.height) // 2
        canvas.paste(diagram, (left, top), diagram)

    canvas.save(path, format="PNG", optimize=True)


def _save(source: str, path: Path, *, width_px: int) -> None:
    document = parse_mermaid(source, strict=True)
    document.save(
        path,
        width_px=width_px,
        background="#F8FAFC",
        style="official",
        theme=BASE_THEME,
    )


def main(output_directory: str = "docs/assets/readme") -> None:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _build_hero(output / "diagram-pptx-gallery.png")
    _save(ORDER_FLOW, output / "order-fulfillment-flow.png", width_px=2200)
    _save(CHECKOUT_SEQUENCE, output / "checkout-sequence.png", width_px=1900)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/assets/readme")
