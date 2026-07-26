"""Build public, fictional README screenshots with diagram-pptx itself."""

from __future__ import annotations

import sys
from pathlib import Path

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
    _save(ORDER_FLOW, output / "order-fulfillment-flow.png", width_px=2200)
    _save(CHECKOUT_SEQUENCE, output / "checkout-sequence.png", width_px=1900)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/assets/readme")
