import re

from .constants import Field, Limit


class LinePick:
    pattern = re.compile(r"(?:error\s+line|on\s+line|\bline)\s+(\d+)", re.IGNORECASE)

    @staticmethod
    def choose(message: str, reported: int | None = None, hash_line: int | None = None) -> int | None:
        match = LinePick.pattern.search(message or "")
        if match:
            return int(match.group(1))
        if reported is not None and int(reported) > 0:
            return int(reported)
        if hash_line is not None and int(hash_line) >= 0:
            return int(hash_line) + 1
        return None


class Caret:
    marks = set("- \t^")

    @staticmethod
    def column(message: str) -> int | None:
        for row in (message or "").splitlines():
            if "^" in row and set(row) <= Caret.marks:
                return row.index("^") + 1
        return None


class Excerpt:
    @staticmethod
    def build(source: str, line: int | None) -> str:
        if not line or not source:
            return ""
        rows = source.splitlines()
        if line > len(rows):
            return ""
        start = max(1, line - Limit.excerpt)
        end = min(len(rows), line + Limit.excerpt)
        picked = []
        for number in range(start, end + 1):
            mark = ">" if number == line else " "
            picked.append(f"{mark} {number}: {rows[number - 1]}")
        return "\n".join(picked)


class Hint:
    @staticmethod
    def build(engine: str, line: int | None, repairable: bool) -> str:
        if not repairable:
            return "This failure is in the local renderer setup. Fix the missing dependency and call the tool again."
        if line:
            return (
                f"{engine} rejected line {line}. "
                "Edit that line in the source, then call the same tool again with the corrected source."
            )
        return (
            f"{engine} rejected the input. "
            "Read diagnostics and excerpt, fix the source, then call the same tool again."
        )


class Notes:
    @staticmethod
    def lines(text: str, limit: int = 20) -> list[str]:
        rows = []
        for row in (text or "").splitlines():
            clean = row.strip()
            if not clean:
                continue
            rows.append(clean[:500])
            if len(rows) >= limit:
                break
        return rows


class Diag:
    @staticmethod
    def ok(engine: str, **extra) -> dict:
        data = {Field.ok: True, Field.engine: engine, Field.repairable: False}
        data.update(extra)
        return data

    @staticmethod
    def fail(
        engine: str,
        source: str,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        hash_line: int | None = None,
        diagnostics: list[str] | None = None,
        repairable: bool = True,
        hint: str | None = None,
        **extra,
    ) -> dict:
        picked = LinePick.choose(message, line, hash_line)
        col = column if column else Caret.column(message)
        payload = {
            Field.ok: False,
            Field.engine: engine,
            Field.repairable: repairable,
            Field.message: (message or "render failed").strip(),
            Field.line: picked,
            Field.column: col,
            Field.excerpt: Excerpt.build(source, picked),
            Field.diagnostics: diagnostics if diagnostics is not None else Notes.lines(message),
            Field.hint: hint or Hint.build(engine, picked, repairable),
        }
        payload.update(extra)
        return payload
