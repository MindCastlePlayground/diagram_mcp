import json

from .constants import (
    Engine,
    Field,
    Format,
    JsonKey,
    RpcValue,
    Theme,
    Tool,
    ToolDesc,
)
from .diagnostics import Diag
from .engines import Engines


class Schema:
    @staticmethod
    def text(description: str) -> dict:
        return {JsonKey.type: RpcValue.string, JsonKey.description: description}

    @staticmethod
    def choice(values: tuple[str, ...], description: str) -> dict:
        return {JsonKey.type: RpcValue.string, JsonKey.enum: list(values), JsonKey.description: description}

    @staticmethod
    def scene() -> dict:
        return {
            JsonKey.description: "Excalidraw document, elements array, or {nodes, edges}. A JSON string is also accepted.",
        }

    @staticmethod
    def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {
            JsonKey.name: name,
            JsonKey.description: description,
            JsonKey.input_schema: {
                JsonKey.type: RpcValue.object,
                JsonKey.properties: properties,
                JsonKey.required: required,
                "additionalProperties": False,
            },
        }


class ToolCatalog:
    @staticmethod
    def list() -> list[dict]:
        shared = {
            Field.engine: Schema.choice(Engine.values, "Diagram engine."),
            Field.source: Schema.text("Diagram source. Use this or input_path for Mermaid and PlantUML."),
            Field.input_path: Schema.text("UTF-8 file to read when source or scene is omitted."),
            Field.theme: Schema.choice(Theme.values, "Mermaid theme."),
            Field.background: Schema.text("CSS background color for Mermaid. Default white."),
        }
        render_props = dict(shared)
        render_props[Field.scene] = Schema.scene()
        render_props[Field.format] = Schema.choice(Format.values, "Output format. Default svg.")
        render_props[Field.output_path] = Schema.text("File to write. Default is under .diagram_mcp/output or DIAGRAM_MCP_HOME.")
        compile_props = dict(shared)
        compile_props[Field.scene] = Schema.scene()
        return [
            Schema.tool(Tool.compile, ToolDesc.compile, compile_props, [Field.engine]),
            Schema.tool(Tool.render, ToolDesc.render, render_props, [Field.engine]),
            Schema.tool(Tool.status, ToolDesc.status, {}, []),
        ]


class Present:
    @staticmethod
    def of(payload: dict) -> dict:
        summary = Present.summary(payload)
        text = summary + "\n" + json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            JsonKey.content: [{JsonKey.type: RpcValue.text, JsonKey.text: text}],
            JsonKey.structured: payload,
            JsonKey.is_error: not bool(payload.get(Field.ok)),
        }

    @staticmethod
    def summary(payload: dict) -> str:
        engine = str(payload.get(Field.engine) or "diagram")
        if payload.get(Field.ok):
            path = payload.get(Field.output_path)
            if path:
                return f"{engine} rendered {path}"
            return f"{engine} ok"
        message = str(payload.get(Field.message) or "render failed").splitlines()[0]
        line = payload.get(Field.line)
        if line:
            return f"{engine} error on line {line}: {message}"
        return f"{engine} error: {message}"


class ToolService:
    def call(self, name: str, args: dict | None) -> dict:
        args = args or {}
        if not isinstance(args, dict):
            payload = Diag.fail("diagram", "", "arguments must be an object", repairable=True)
            return Present.of(payload)
        try:
            if name == Tool.compile:
                payload = Engines.compile(args)
            elif name == Tool.render:
                payload = Engines.render(args)
            elif name == Tool.status:
                payload = Engines.status()
            else:
                payload = Diag.fail("diagram", "", f"unknown tool {name}", repairable=False)
        except ValueError as exc:
            payload = Diag.fail(str(args.get(Field.engine) or "diagram"), "", str(exc), repairable=True)
        except json.JSONDecodeError as exc:
            payload = Diag.fail(Engine.excalidraw, "", f"scene is not valid JSON: {exc}", repairable=True)
        except OSError as exc:
            payload = Diag.fail(str(args.get(Field.engine) or "diagram"), "", str(exc), repairable=False)
        except Exception as exc:
            payload = Diag.fail(
                str(args.get(Field.engine) or "diagram"),
                "",
                str(exc),
                repairable=False,
                hint="The renderer failed before it could check the diagram. Read the message and retry after the environment is fixed.",
            )
        return Present.of(payload)
