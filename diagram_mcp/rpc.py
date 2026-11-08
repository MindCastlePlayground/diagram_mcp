import json
import sys

from .constants import JsonKey, Meta, Msg, RpcError, RpcMethod, RpcValue
from .tools import ToolCatalog, ToolService


class StdioClosed(Exception):
    pass


class Response:
    @staticmethod
    def ok(req_id, result: dict) -> dict:
        return {JsonKey.jsonrpc: RpcValue.version, JsonKey.id: req_id, JsonKey.result: result}

    @staticmethod
    def err(req_id, code: int, message: str) -> dict:
        return {
            JsonKey.jsonrpc: RpcValue.version,
            JsonKey.id: req_id,
            JsonKey.error: {JsonKey.code: code, JsonKey.message: message},
        }


class McpServer:
    def __init__(self, service: ToolService | None = None):
        self.service = service or ToolService()

    def handle(self, req: dict) -> dict | None:
        if not isinstance(req, dict):
            return Response.err(None, RpcError.invalid_request, Msg.invalid_request)
        req_id = req.get(JsonKey.id)
        method = req.get(JsonKey.method)
        params = req.get(JsonKey.params, {})
        if method == RpcMethod.initialized:
            return None
        if method == RpcMethod.initialize:
            return Response.ok(req_id, self.init(params if isinstance(params, dict) else {}))
        if method == RpcMethod.ping:
            return Response.ok(req_id, {})
        if method == RpcMethod.tools_list:
            return Response.ok(req_id, {JsonKey.tools: ToolCatalog.list()})
        if method == RpcMethod.tools_call:
            return Response.ok(req_id, self.call(params))
        return Response.err(req_id, RpcError.method_not_found, str(method))

    def init(self, params: dict) -> dict:
        version = params.get(JsonKey.protocol_version, Meta.protocol)
        return {
            JsonKey.protocol_version: version,
            JsonKey.capabilities: {JsonKey.tools: {JsonKey.list_changed: False}},
            JsonKey.server_info: {JsonKey.name: Meta.name, JsonKey.version: Meta.version},
        }

    def call(self, params: dict) -> dict:
        if not isinstance(params, dict):
            return self.service.call("", {})
        name = str(params.get(JsonKey.name, ""))
        args = params.get(JsonKey.arguments, {})
        return self.service.call(name, args if isinstance(args, dict) else {})


class StdioApp:
    def __init__(self, server: McpServer | None = None):
        self.server = server or McpServer()

    def run(self) -> None:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip().lstrip("\ufeff")
            if not line:
                continue
            try:
                self.once(line)
            except StdioClosed:
                break

    def once(self, line: str) -> None:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            self.write(Response.err(None, RpcError.parse, Msg.invalid_json))
            return
        try:
            res = self.server.handle(req)
        except Exception as exc:
            req_id = req.get(JsonKey.id) if isinstance(req, dict) else None
            res = Response.err(req_id, RpcError.internal, str(exc))
        if res is not None:
            self.write(res)

    def write(self, res: dict) -> None:
        try:
            sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, OSError) as exc:
            raise StdioClosed(str(exc)) from exc
