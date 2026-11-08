class Meta:
    name = "diagram-mcp"
    version = "1.0.0"
    protocol = "2025-06-18"


class JsonKey:
    jsonrpc = "jsonrpc"
    id = "id"
    method = "method"
    params = "params"
    result = "result"
    error = "error"
    code = "code"
    message = "message"
    protocol_version = "protocolVersion"
    capabilities = "capabilities"
    server_info = "serverInfo"
    name = "name"
    version = "version"
    tools = "tools"
    list_changed = "listChanged"
    arguments = "arguments"
    content = "content"
    type = "type"
    text = "text"
    is_error = "isError"
    structured = "structuredContent"
    input_schema = "inputSchema"
    description = "description"
    properties = "properties"
    required = "required"
    additional = "additionalProperties"
    enum = "enum"
    items = "items"


class RpcMethod:
    initialize = "initialize"
    initialized = "notifications/initialized"
    ping = "ping"
    tools_list = "tools/list"
    tools_call = "tools/call"


class RpcValue:
    version = "2.0"
    object = "object"
    string = "string"
    text = "text"


class RpcError:
    parse = -32700
    invalid_request = -32600
    method_not_found = -32601
    invalid_params = -32602
    internal = -32603


class Engine:
    mermaid = "mermaid"
    plantuml = "plantuml"
    excalidraw = "excalidraw"
    values = (mermaid, plantuml, excalidraw)


class Format:
    svg = "svg"
    png = "png"
    values = (svg, png)
    default = svg


class Tool:
    compile = "diagram_compile"
    render = "diagram_render"
    status = "diagram_status"


class ToolDesc:
    compile = (
        "Check Mermaid, PlantUML, or Excalidraw input. "
        "Syntax failures return repairable=true with line, excerpt, and hint so the source can be fixed."
    )
    render = (
        "Render Mermaid, PlantUML, or Excalidraw to SVG or PNG. "
        "Mermaid and PlantUML errors include the failing line and a hint. "
        "Excalidraw accepts a scene, an elements array, or {nodes, edges}."
    )
    status = "Report whether Java, the PlantUML jar, Node, Mermaid, and Playwright Chromium are available."


class Field:
    engine = "engine"
    source = "source"
    input_path = "input_path"
    scene = "scene"
    format = "format"
    output_path = "output_path"
    theme = "theme"
    background = "background"
    ok = "ok"
    repairable = "repairable"
    line = "line"
    column = "column"
    excerpt = "excerpt"
    diagnostics = "diagnostics"
    hint = "hint"
    message = "message"
    bytes = "bytes"
    warnings = "warnings"
    diagram_type = "diagram_type"
    elements = "elements"


class Theme:
    values = ("default", "base", "dark", "forest", "neutral")
    default = "default"


class Default:
    background = "white"
    timeout = 90


class Limit:
    source = 1_000_000
    excerpt = 2


class Env:
    home = "DIAGRAM_MCP_HOME"
    timeout = "DIAGRAM_MCP_TIMEOUT"


class PathName:
    script = "render.js"
    vendor = "vendor"
    jar = "plantuml.jar"
    bundle = ("node_modules", "mermaid", "dist", "mermaid.min.js")
    state = ".diagram_mcp"
    output = "output"
    node = "node"
    java = "java"


class Jar:
    version = "1.2026.9"
    url = "https://github.com/plantuml/plantuml/releases/download/v1.2026.9/plantuml-1.2026.9.jar"


class Marker:
    syntax = "Syntax Error"
    plant_error = "Error line"
    plant_some = "Some diagram description contains errors"
    not_diagram = "not a diagram"


class Msg:
    invalid_json = "invalid json"
    invalid_request = "invalid request"
    stdio_closed = "stdio closed"
    need_source = "source or input_path is required"
    need_scene = "scene or input_path is required for excalidraw"
    bad_engine = "engine must be mermaid, plantuml, or excalidraw"
    bad_format = "format must be svg or png"
    bad_theme = "theme must be default, base, dark, forest, or neutral"
    source_large = "source exceeds 1000000 characters"
    empty_renderer = "renderer returned no JSON"
    java_missing = "java is not installed"
    jar_missing = "PlantUML jar is missing; run setup.sh"
    node_missing = "node is not installed"
    bundle_missing = "mermaid bundle is missing; run npm install"
    timeout = "renderer timed out"
