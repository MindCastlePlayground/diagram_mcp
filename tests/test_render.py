import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diagram_mcp.constants import Field, Tool
from diagram_mcp.diagnostics import Caret, Excerpt, LinePick
from diagram_mcp.tools import ToolService


PUML_OK = "@startuml\nAlice -> Bob: hello\n@enduml\n"
PUML_BAD = "@startuml\nAlice -> Bob: ok\nthis is garbage $$$\n@enduml\n"
PUML_CLASS = "@startuml\nclass A\nclass B\nA --> B\n@enduml\n"
MERMAID_OK = "flowchart LR\n  A[Start] --> B[End]\n"
MERMAID_BAD = "flowchart LR\n  A[Start] --> B[End]\n  this is garbage $$$\n"
SCENE = {
    "nodes": [
        {"id": "a", "label": "Cast", "shape": "rectangle"},
        {"id": "b", "label": "Draw", "shape": "ellipse"},
    ],
    "edges": [{"from": "a", "to": "b", "label": "next"}],
}


class DiagTests(unittest.TestCase):
    def test_line_excerpt_and_caret(self):
        self.assertEqual(LinePick.choose("Parse error on line 4:\nfoo", None), 4)
        self.assertEqual(LinePick.choose("Error line 3 in file: x.puml", None), 3)
        self.assertEqual(LinePick.choose("no digits", 0, 2), 3)
        message = "oops\n----^\n"
        self.assertEqual(Caret.column(message), 5)
        source = "one\ntwo\nthree\nfour"
        excerpt = Excerpt.build(source, 3)
        self.assertIn("> 3: three", excerpt)
        self.assertIn("  2: two", excerpt)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.service = ToolService()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def out(self, name: str) -> str:
        return str(Path(self.tmp.name) / name)

    def call(self, name: str, args: dict) -> dict:
        result = self.service.call(name, args)
        self.assertIn("content", result)
        return result

    def body(self, result: dict) -> dict:
        return result["structuredContent"]

    def test_status_sees_local_engines(self):
        data = self.body(self.call(Tool.status, {}))
        self.assertTrue(data[Field.ok])
        self.assertFalse(result_is_error(self.call(Tool.status, {})))
        self.assertTrue(data["engines"]["plantuml"]["java"])
        self.assertTrue(data["engines"]["plantuml"]["jar"])
        self.assertTrue(data["engines"]["mermaid"]["bundle"])

    def test_plantuml_svg_png_and_class(self):
        svg = self.body(self.call(Tool.render, {
            Field.engine: "plantuml",
            Field.format: "svg",
            Field.source: PUML_OK,
            Field.output_path: self.out("ok.svg"),
        }))
        self.assertTrue(svg[Field.ok])
        text = Path(svg[Field.output_path]).read_text(encoding="utf-8")
        self.assertIn("<svg", text)
        self.assertNotIn("Syntax Error", text)
        png = self.body(self.call(Tool.render, {
            Field.engine: "plantuml",
            Field.format: "png",
            Field.source: PUML_OK,
            Field.output_path: self.out("ok.png"),
        }))
        self.assertGreater(png[Field.bytes], 100)
        drawn = self.body(self.call(Tool.render, {
            Field.engine: "plantuml",
            Field.format: "svg",
            Field.source: PUML_CLASS,
            Field.output_path: self.out("class.svg"),
        }))
        self.assertTrue(drawn[Field.ok], drawn)

    def test_plantuml_syntax_error_is_repairable(self):
        result = self.call(Tool.render, {
            Field.engine: "plantuml",
            Field.format: "svg",
            Field.source: PUML_BAD,
            Field.output_path: self.out("bad.svg"),
        })
        self.assertTrue(result["isError"])
        data = self.body(result)
        self.assertFalse(data[Field.ok])
        self.assertTrue(data[Field.repairable])
        self.assertEqual(data[Field.line], 3)
        self.assertIn("garbage", data[Field.excerpt])
        self.assertIn("line 3", data[Field.hint])
        self.assertIn("plantuml error on line 3", result["content"][0]["text"].splitlines()[0].lower())
        self.assertFalse(Path(self.out("bad.svg")).exists())

    def test_plantuml_compile_rejects_garbage(self):
        data = self.body(self.call(Tool.compile, {Field.engine: "plantuml", Field.source: PUML_BAD}))
        self.assertEqual(data[Field.line], 3)
        self.assertTrue(data[Field.repairable])

    def test_excalidraw_svg_and_png(self):
        svg = self.body(self.call(Tool.render, {
            Field.engine: "excalidraw",
            Field.format: "svg",
            Field.scene: SCENE,
            Field.output_path: self.out("draw.svg"),
        }))
        self.assertTrue(svg[Field.ok], svg)
        text = Path(svg[Field.output_path]).read_text(encoding="utf-8")
        self.assertIn("<svg", text)
        self.assertIn("Cast", text)
        self.assertIn("Draw", text)
        png = self.body(self.call(Tool.render, {
            Field.engine: "excalidraw",
            Field.format: "png",
            Field.scene: json.dumps(SCENE),
            Field.output_path: self.out("draw.png"),
        }))
        self.assertTrue(png[Field.ok], png)
        self.assertGreater(png[Field.bytes], 100)

    def test_excalidraw_elements_and_bad_scene(self):
        elements = [
            {"type": "rectangle", "x": 10, "y": 10, "width": 80, "height": 40, "label": "Box"},
            {"type": "arrow", "x": 90, "y": 30, "points": [[0, 0], [40, 0]]},
        ]
        data = self.body(self.call(Tool.compile, {Field.engine: "excalidraw", Field.scene: elements}))
        self.assertTrue(data[Field.ok])
        self.assertEqual(data["elements"], 2)
        bad = self.body(self.call(Tool.render, {Field.engine: "excalidraw", Field.scene: {"nope": 1}}))
        self.assertFalse(bad[Field.ok])
        self.assertTrue(bad[Field.repairable])

    def test_mermaid_good_and_bad(self):
        good = self.body(self.call(Tool.render, {
            Field.engine: "mermaid",
            Field.format: "svg",
            Field.source: MERMAID_OK,
            Field.output_path: self.out("m.svg"),
        }))
        self.assertTrue(good[Field.ok], good)
        text = Path(good[Field.output_path]).read_text(encoding="utf-8")
        self.assertIn("<svg", text)
        self.assertIn("Start", text)
        png = self.body(self.call(Tool.render, {
            Field.engine: "mermaid",
            Field.format: "png",
            Field.source: MERMAID_OK,
            Field.output_path: self.out("m.png"),
        }))
        self.assertTrue(png[Field.ok], png)
        self.assertGreater(png[Field.bytes], 100)
        result = self.call(Tool.render, {
            Field.engine: "mermaid",
            Field.source: MERMAID_BAD,
            Field.output_path: self.out("mbad.svg"),
        })
        self.assertTrue(result["isError"])
        data = self.body(result)
        self.assertTrue(data[Field.repairable])
        self.assertEqual(data[Field.line], 3)
        self.assertIn("garbage", data[Field.excerpt])
        self.assertIn("line 3", data[Field.hint])
        self.assertFalse(Path(self.out("mbad.svg")).exists())


class StdioTests(unittest.TestCase):
    def test_protocol_reports_plantuml_error(self):
        env = os.environ.copy()
        proc = subprocess.Popen(
            [sys.executable, "-m", "diagram_mcp"],
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            def send(payload, expect=True):
                assert proc.stdin is not None and proc.stdout is not None
                proc.stdin.write(json.dumps(payload) + "\n")
                proc.stdin.flush()
                if not expect:
                    return None
                line = proc.stdout.readline()
                self.assertTrue(line, "stdio returned no response")
                return json.loads(line)

            init = send({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
            })
            self.assertEqual(init["result"]["serverInfo"]["name"], "diagram-mcp")
            send({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect=False)
            listed = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = [item["name"] for item in listed["result"]["tools"]]
            self.assertEqual(names, ["diagram_compile", "diagram_render", "diagram_status"])
            called = send({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "diagram_render",
                    "arguments": {"engine": "plantuml", "format": "svg", "source": PUML_BAD},
                },
            })
            self.assertTrue(called["result"]["isError"])
            structured = called["result"]["structuredContent"]
            self.assertEqual(structured["line"], 3)
            self.assertTrue(structured["repairable"])
        finally:
            if proc.stdin:
                proc.stdin.close()
            proc.kill()
            proc.wait(timeout=5)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()


def result_is_error(result: dict) -> bool:
    return bool(result["isError"])


if __name__ == "__main__":
    unittest.main()
