# AGENTS.md

## Project Rules

1. Keep protocol, diagnostics, and engine calls in separate modules.
2. Mermaid and PlantUML failures must stay visible to the caller: `ok` false, `isError` true, and `line` / `excerpt` / `hint` when the engine reports a location.
3. Do not treat a PlantUML error image as a successful render. A non-zero exit or an SVG that contains `Syntax Error` is a failure.
4. Pin the PlantUML jar in `setup.sh`. Do not commit `vendor/*.jar` or `node_modules`.

## Git And Push Policy

1. The agent may commit and push directly to `origin/main` when the user asks to commit, push, publish, or finish a completed implementation.
2. Stage explicit paths only. Do not use `git add -A`.
