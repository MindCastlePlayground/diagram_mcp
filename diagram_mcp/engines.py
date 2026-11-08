import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from .constants import (
    Default,
    Engine,
    Env,
    Field,
    Format,
    Jar,
    Limit,
    Marker,
    Msg,
    PathName,
    Theme,
)
from .diagnostics import Diag, Notes


class Paths:
    @staticmethod
    def root() -> Path:
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def script() -> Path:
        return Paths.root() / PathName.script

    @staticmethod
    def jar() -> Path:
        return Paths.root() / PathName.vendor / PathName.jar

    @staticmethod
    def bundle() -> Path:
        return Paths.root().joinpath(*PathName.bundle)

    @staticmethod
    def timeout() -> int:
        raw = os.environ.get(Env.timeout, "")
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return Default.timeout

    @staticmethod
    def output(engine: str, fmt: str, requested: str | None) -> Path:
        if requested:
            path = Path(requested).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        base = os.environ.get(Env.home)
        folder = Path(base).expanduser() if base else Path.cwd() / PathName.state
        folder = folder / PathName.output
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return folder / f"{engine}-{stamp}-{uuid.uuid4().hex[:8]}.{fmt}"


class Args:
    @staticmethod
    def engine(args: dict, allowed: tuple[str, ...]) -> str:
        engine = str(args.get(Field.engine, "")).strip().lower()
        if engine not in allowed:
            raise ValueError(Msg.bad_engine)
        return engine

    @staticmethod
    def fmt(args: dict) -> str:
        fmt = str(args.get(Field.format, Format.default)).strip().lower()
        if fmt not in Format.values:
            raise ValueError(Msg.bad_format)
        return fmt

    @staticmethod
    def theme(args: dict) -> str:
        theme = str(args.get(Field.theme, Theme.default)).strip().lower() or Theme.default
        if theme not in Theme.values:
            raise ValueError(Msg.bad_theme)
        return theme

    @staticmethod
    def source(args: dict) -> str:
        text = args.get(Field.source)
        if text is None or text == "":
            raw = args.get(Field.input_path)
            if not raw:
                raise ValueError(Msg.need_source)
            text = Path(str(raw)).expanduser().read_text(encoding="utf-8")
        source = str(text)
        if len(source) > Limit.source:
            raise ValueError(Msg.source_large)
        return source

    @staticmethod
    def scene(args: dict):
        if Field.scene in args and args.get(Field.scene) not in (None, ""):
            scene = args[Field.scene]
        else:
            raw = args.get(Field.input_path)
            if not raw:
                raise ValueError(Msg.need_scene)
            scene = Path(str(raw)).expanduser().read_text(encoding="utf-8")
        if isinstance(scene, str):
            scene = json.loads(scene)
        return scene


class Node:
    @staticmethod
    def run(payload: dict) -> dict:
        if shutil.which(PathName.node) is None:
            raise RuntimeError(Msg.node_missing)
        proc = subprocess.run(
            [PathName.node, str(Paths.script())],
            input=json.dumps(payload).encode("utf-8"),
            cwd=str(Paths.root()),
            capture_output=True,
            timeout=Paths.timeout(),
            check=False,
        )
        text = proc.stdout.decode("utf-8", "replace").strip()
        if not text:
            err = proc.stderr.decode("utf-8", "replace")[-2000:]
            raise RuntimeError(err or f"{Msg.empty_renderer} (exit {proc.returncode})")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            err = proc.stderr.decode("utf-8", "replace")[-1000:]
            raise RuntimeError(f"{Msg.empty_renderer}: {exc}; {err}") from exc
        if not isinstance(data, dict):
            raise RuntimeError(Msg.empty_renderer)
        return data


class Plantuml:
    @staticmethod
    def available() -> dict:
        jar = Paths.jar()
        return {
            "java": shutil.which(PathName.java) is not None,
            "jar": jar.is_file() and jar.stat().st_size > 1_000_000,
            "version": Jar.version,
        }

    @staticmethod
    def render(source: str, fmt: str, output: Path | None) -> dict:
        info = Plantuml.available()
        if not info["java"]:
            return Diag.fail(Engine.plantuml, source, Msg.java_missing, repairable=False)
        if not info["jar"]:
            return Diag.fail(Engine.plantuml, source, Msg.jar_missing, repairable=False)
        work = Path(tempfile.mkdtemp(prefix="diagram-puml-"))
        try:
            src = work / "diagram.puml"
            src.write_text(source, encoding="utf-8")
            cmd = [
                PathName.java,
                "-Djava.awt.headless=true",
                "-jar",
                str(Paths.jar()),
                "-charset",
                "UTF-8",
                f"--{fmt}",
                "--stop-on-error",
                "--output-dir",
                str(work),
                str(src),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=Paths.timeout(),
                check=False,
            )
            produced = sorted(work.glob(f"diagram*.{fmt}"))
            svg_text = ""
            if fmt == Format.svg:
                for item in produced:
                    svg_text += item.read_text(encoding="utf-8", errors="replace")
            stderr = proc.stderr or ""
            stdout = proc.stdout or ""
            if Plantuml.bad(proc.returncode, stderr, stdout, svg_text):
                notes = Notes.lines(stderr + "\n" + stdout)
                if Marker.syntax in svg_text and Marker.syntax not in " ".join(notes):
                    notes.append(Marker.syntax)
                message = Plantuml.message(proc.returncode, stderr, stdout, svg_text)
                return Diag.fail(
                    Engine.plantuml,
                    source,
                    message,
                    diagnostics=notes,
                    exit_code=proc.returncode,
                )
            if not produced:
                return Diag.fail(
                    Engine.plantuml,
                    source,
                    "PlantUML exited without an output file",
                    diagnostics=Notes.lines(stderr + "\n" + stdout),
                    repairable=False,
                    exit_code=proc.returncode,
                )
            if output is None:
                return Diag.ok(Engine.plantuml, format=fmt, diagram_type="plantuml")
            saved = Plantuml.publish(produced, output)
            return Diag.ok(
                Engine.plantuml,
                format=fmt,
                output_path=str(saved[0]),
                output_paths=[str(item) for item in saved],
                bytes=saved[0].stat().st_size,
                warnings=Notes.lines(stderr),
            )
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @staticmethod
    def bad(code: int, stderr: str, stdout: str, svg: str) -> bool:
        if code != 0:
            return True
        if svg and Marker.syntax in svg:
            return True
        blob = f"{stderr}\n{stdout}"
        return Marker.plant_some in blob or Marker.plant_error in blob

    @staticmethod
    def message(code: int, stderr: str, stdout: str, svg: str) -> str:
        rows = f"{stderr}\n{stdout}".splitlines()
        for row in rows:
            if Marker.plant_error in row:
                return row.strip()
        for row in rows:
            if "Error" in row and "Dot executable" not in row:
                return row.strip()
        if svg and Marker.syntax in svg:
            return "PlantUML wrote a diagram that contains Syntax Error"
        if Marker.not_diagram in (stderr + stdout).lower():
            return "PlantUML did not find a diagram. Wrap the source in @startuml and @enduml."
        return f"PlantUML failed with exit code {code}"

    @staticmethod
    def publish(produced: list[Path], output: Path) -> list[Path]:
        saved = []
        for index, item in enumerate(produced):
            dest = output if index == 0 else output.with_name(f"{output.stem}-{index + 1}{output.suffix}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, dest)
            saved.append(dest)
        return saved


class Mermaid:
    @staticmethod
    def available() -> dict:
        return {
            "node": shutil.which(PathName.node) is not None,
            "bundle": Paths.bundle().is_file(),
            "script": Paths.script().is_file(),
        }

    @staticmethod
    def run(source: str, fmt: str, output: Path | None, theme: str, background: str) -> dict:
        info = Mermaid.available()
        if not info["node"]:
            return Diag.fail(Engine.mermaid, source, Msg.node_missing, repairable=False)
        if not info["bundle"] or not info["script"]:
            return Diag.fail(Engine.mermaid, source, Msg.bundle_missing, repairable=False)
        payload = {
            "action": "compile" if output is None else "mermaid",
            "source": source,
            "format": fmt,
            "theme": theme,
            "background": background,
        }
        if output is not None:
            payload["output"] = str(output)
        try:
            data = Node.run(payload)
        except subprocess.TimeoutExpired:
            return Diag.fail(Engine.mermaid, source, Msg.timeout, repairable=False)
        if not data.get(Field.ok):
            return Diag.fail(
                Engine.mermaid,
                source,
                str(data.get(Field.message) or "Mermaid rejected the diagram"),
                line=data.get(Field.line),
                column=data.get(Field.column),
                hash_line=data.get("hashLine"),
                diagnostics=Notes.lines(str(data.get(Field.message) or "")),
                token=data.get("token"),
                expected=data.get("expected"),
            )
        if output is None:
            return Diag.ok(Engine.mermaid, diagram_type=data.get("type"))
        if not output.is_file():
            return Diag.fail(Engine.mermaid, source, "Mermaid did not write the output file", repairable=False)
        return Diag.ok(
            Engine.mermaid,
            format=fmt,
            output_path=str(output),
            bytes=output.stat().st_size,
            diagram_type=data.get("type"),
        )


class Excalidraw:
    @staticmethod
    def run(scene, fmt: str, output: Path | None) -> dict:
        if shutil.which(PathName.node) is None:
            return Diag.fail(Engine.excalidraw, "", Msg.node_missing, repairable=False)
        payload = {"action": "excalidraw", "scene": scene, "format": fmt}
        if output is not None:
            payload["output"] = str(output)
        try:
            data = Node.run(payload)
        except subprocess.TimeoutExpired:
            return Diag.fail(Engine.excalidraw, "", Msg.timeout, repairable=False)
        except RuntimeError as exc:
            return Diag.fail(Engine.excalidraw, "", str(exc), repairable=True)
        if not data.get(Field.ok):
            return Diag.fail(
                Engine.excalidraw,
                "",
                str(data.get(Field.message) or "Excalidraw scene was rejected"),
                repairable=True,
            )
        if output is None:
            return Diag.ok(
                Engine.excalidraw,
                elements=data.get("elements"),
                warnings=data.get("warnings") or [],
            )
        if not output.is_file():
            return Diag.fail(Engine.excalidraw, "", "Excalidraw did not write the output file", repairable=False)
        return Diag.ok(
            Engine.excalidraw,
            format=fmt,
            output_path=str(output),
            bytes=output.stat().st_size,
            elements=data.get("elements"),
            warnings=data.get("warnings") or [],
        )


class Engines:
    @staticmethod
    def compile(args: dict) -> dict:
        engine = Args.engine(args, Engine.values)
        if engine == Engine.excalidraw:
            return Excalidraw.run(Args.scene(args), Format.svg, None)
        source = Args.source(args)
        if engine == Engine.plantuml:
            return Plantuml.render(source, Format.svg, None)
        return Mermaid.run(source, Format.svg, None, Args.theme(args), str(args.get(Field.background) or Default.background))

    @staticmethod
    def render(args: dict) -> dict:
        engine = Args.engine(args, Engine.values)
        fmt = Args.fmt(args)
        output = Paths.output(engine, fmt, args.get(Field.output_path))
        if engine == Engine.excalidraw:
            return Excalidraw.run(Args.scene(args), fmt, output)
        source = Args.source(args)
        if engine == Engine.plantuml:
            return Plantuml.render(source, fmt, output)
        return Mermaid.run(
            source,
            fmt,
            output,
            Args.theme(args),
            str(args.get(Field.background) or Default.background),
        )

    @staticmethod
    def status() -> dict:
        return Diag.ok(
            "diagram",
            engines={
                Engine.mermaid: Mermaid.available(),
                Engine.plantuml: Plantuml.available(),
                Engine.excalidraw: {
                    "node": shutil.which(PathName.node) is not None,
                    "roughjs": (Paths.root() / "node_modules" / "roughjs").is_dir(),
                    "jsdom": (Paths.root() / "node_modules" / "jsdom").is_dir(),
                },
            },
            formats=list(Format.values),
            jar=Jar.url,
        )
