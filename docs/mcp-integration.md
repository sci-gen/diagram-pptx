# MCP and Codex integration

`diagram-pptx` is a provider-neutral Python library. The core package does not
emit OpenAI, Anthropic, or MCP tool-definition formats and does not depend on
an MCP SDK.

An integration should be a small, separate adapter:

```text
LLM client
  -> MCP tool with typed inputs
  -> diagram-pptx + python-pptx
  -> editable .pptx
```

The MCP SDK derives JSON Schema from the adapter's typed handler signature.
There is no reason for `diagram-pptx` itself to maintain a second,
provider-specific schema generator. `CompileResult.to_dict()` is only a
generic, JSON-safe operation summary; it is not a tool-definition format.

## Minimal MCP server

Install the MCP SDK in the adapter environment, not as a core
`diagram-pptx` dependency:

```bash
python -m venv .venv
.venv/bin/python -m pip install diagram-pptx mcp
```

On Windows, use `.venv\Scripts\python.exe` in place of
`.venv/bin/python`.

The following `server.py` exposes one read-only inspection tool and one
write tool. Pydantic constraints and `Literal` choices become the MCP input
schema automatically.

```python
from pathlib import Path
from typing import Annotated, Literal

from diagram_pptx import parse_mermaid, render_mermaid
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pptx import Presentation
from pydantic import Field


Backend = Literal["native", "official", "auto"]
Position = Literal["full", "left", "right", "top", "bottom"]

mcp = FastMCP(
    "diagram-pptx",
    instructions=(
        "Create editable PowerPoint diagrams from Mermaid. "
        "Prefer inspect_mermaid before writing complex diagrams. "
        "Output paths must be new absolute .pptx paths."
    ),
)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    structured_output=True,
)
def inspect_mermaid(
    source: Annotated[str, Field(description="Complete Mermaid source.")],
    strict: bool = False,
) -> dict:
    """Inspect syntax support without creating a file."""
    document = parse_mermaid(source, strict=strict)
    return {
        "diagram_kind": document.model.kind,
        "is_fully_modeled": document.is_fully_modeled,
        "modeling_rate": document.modeling_rate,
        "required_backend": document.required_backend,
        "diagnostics": [item.to_dict() for item in document.diagnostics],
    }


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
    structured_output=True,
)
def create_diagram_presentation(
    source: Annotated[str, Field(description="Complete Mermaid source.")],
    output_path: Annotated[
        str,
        Field(description="Absolute path for a new .pptx file."),
    ],
    position: Position = "full",
    backend: Backend = "native",
    style: Literal["native", "official"] = "native",
    colors: dict | None = None,
) -> dict:
    """Create a one-slide presentation containing one editable diagram."""
    output = Path(output_path).expanduser()
    if not output.is_absolute() or output.suffix.lower() != ".pptx":
        raise ValueError("output_path must be an absolute .pptx path")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = render_mermaid(
        source,
        slide=slide,
        position=position,
        backend=backend,
        style=style,
        colors=colors,
        group=True,
    )
    presentation.save(output)
    return {
        "output_path": str(output),
        "slide_number": 1,
        **result.to_dict(),
    }


if __name__ == "__main__":
    mcp.run("stdio")
```

For production use, prefer a typed Pydantic model over the example's open
`colors: dict | None`. Its fields can mirror `ColorMapStyle`: `name`,
`primary`, `secondary`, `fill`, `decision_fill`, `line`, `edge`, `text`,
`group_line`, and `label_fill`, with numeric positions constrained to
`0..1`.

An `add_diagram_to_presentation` tool can use the same pattern:

1. Require an absolute existing `.pptx` input path.
2. Require a different, new `.pptx` output path.
3. Load it with `Presentation(input_path)`.
4. Select an existing slide or append a blank slide.
5. Call `render_mermaid(...)`, save, and return the output path plus
   `CompileResult.to_dict()`.

Keeping input and output paths separate prevents an agent tool call from
silently overwriting the source deck.

## Register the server directly in Codex

Use absolute paths in `~/.codex/config.toml`:

```toml
[mcp_servers.diagram_pptx]
command = "/absolute/path/to/.venv/bin/python"
args = ["/absolute/path/to/server.py"]
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "writes"
```

On Windows, `command` can point to
`C:\absolute\path\.venv\Scripts\python.exe`. Restart Codex after changing
the MCP configuration.

## Package it as a Codex plugin

A distributable integration can keep the MCP adapter and its operating
guidance together:

```text
diagram-pptx/
├── .codex-plugin/
│   └── plugin.json
├── .mcp.json
├── scripts/
│   └── server.py
└── skills/
    └── diagram-pptx/
        └── SKILL.md
```

Example `.codex-plugin/plugin.json`:

```json
{
  "name": "diagram-pptx",
  "version": "0.1.0",
  "description": "Create editable native PowerPoint diagrams from Mermaid",
  "skills": "./skills/",
  "mcpServers": "./.mcp.json"
}
```

Example `.mcp.json`:

```json
{
  "mcpServers": {
    "diagram-pptx": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/scripts/server.py"],
      "cwd": "/absolute/path/to/diagram-pptx"
    }
  }
}
```

The plugin remains an integration package. It may depend on `mcp`,
`diagram-pptx`, and `python-pptx` in its own virtual environment without
adding MCP to users who only want the Python library.

## Skill example

The skill teaches an agent when and how to call the tools. It does not repeat
their machine-readable schemas.

```markdown
---
name: diagram-pptx
description: Create or edit PowerPoint files with Mermaid diagrams rendered as editable native shapes.
---

# Diagram PPTX

1. Use `inspect_mermaid` first when Native compatibility is uncertain.
2. Use `create_diagram_presentation` for a new deck.
3. Use `add_diagram_to_presentation` for an existing deck.
4. Choose exactly one placement input:
   - `position`: `full`, `left`, `right`, `top`, or `bottom`
   - `relative_bounds`: normalized `[x, y, width, height]`
   - `bounds`: physical inches `[left, top, width, height]`
5. Prefer `backend="native"` unless Official Mermaid geometry is required.
6. `style="official"` changes appearance, not the geometry backend.
7. Use a new absolute `.pptx` output path and never overwrite the input.
8. Return the output path, slide number, backend, and diagnostics.
```

This split gives each layer one responsibility:

- Python types and behavior live in `diagram-pptx`.
- Tool input schema comes from the MCP adapter's typed signatures.
- Agent workflow and defaults live in the skill.
- Client discovery and startup configuration live in the plugin manifest.

## Validation

Before publishing an adapter:

1. Initialize it with an MCP client or the MCP Inspector.
2. Confirm `tools/list` exposes the expected descriptions and constraints.
3. Call the inspection and write tools.
4. Re-open the generated deck with `python-pptx`.
5. Confirm the diagram is a group of editable AutoShapes/connectors and that
   the package contains no full-diagram image `<a:blip>`.

See OpenAI's
[Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
guide for current Codex plugin and MCP guidance, and the
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for
FastMCP server details.
