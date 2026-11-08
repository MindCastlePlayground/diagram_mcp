# diagram_mcp

`diagram_mcp` 是一个本地 stdio MCP。它取代 `MindCastlePlayground/mermaid_mcp` 和 `MindCastlePlayground/uml_mcp`，并把 Excalidraw 场景渲染放进同一个服务。

Mermaid 和 PlantUML 渲染失败时，工具结果带 `isError: true`。正文第一行是错误摘要，后面是 JSON。Agent 可以读 `line`、`column`、`excerpt`、`diagnostics` 和 `hint`，改源码后再调用同一个工具。

## 安装

需要 Python 3.10+、Node.js 20+、npm、JRE 17+。在仓库根目录执行：

```bash
bash setup.sh
```

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

脚本会做三件事：

1. `npm install`，安装 `mermaid`、`playwright`、`roughjs`、`jsdom`。
2. `npx playwright install chromium`，供 Mermaid 和 PNG 截图使用。
3. 下载 PlantUML `1.2026.9` 到 `vendor/plantuml.jar`。jar 不入库。类图和序列图不需要 Graphviz。

Python 侧没有第三方依赖。启动目录必须是本仓库：

```bash
python3 -m diagram_mcp
```

### MCP 客户端

```json
{
  "mcpServers": {
    "diagram-mcp": {
      "command": "python3",
      "args": ["-m", "diagram_mcp"],
      "cwd": "/opt/diagram_mcp"
    }
  }
}
```

`cwd` 是本仓库根目录，不是它的父目录。Playwright 浏览器装在运行用户的缓存里，MCP 进程要使用同一个用户。

输出默认写到当前工作目录的 `.diagram_mcp/output/`。设置 `DIAGRAM_MCP_HOME` 可改这个目录。`DIAGRAM_MCP_TIMEOUT` 是单次渲染秒数，默认 90。

## 工具

| 工具 | 作用 |
| --- | --- |
| `diagram_compile(engine, source? / scene? / input_path?)` | 检查源码或场景，不保留成功文件 |
| `diagram_render(engine, format?, source? / scene?, output_path?)` | 渲染成 `svg` 或 `png` |
| `diagram_status()` | 查看 Java、jar、Node、Mermaid 和 roughjs 是否就绪 |

`engine` 取 `mermaid`、`plantuml`、`excalidraw`。Mermaid 还可传 `theme`（`default`、`base`、`dark`、`forest`、`neutral`）和 `background`。

和旧仓库的对应关系：

| 旧工具 | 现在 |
| --- | --- |
| `mermaid_compile` / `compile_mermaid` | `diagram_compile`，`engine=mermaid` |
| `mermaid_draw` / `render_mermaid_svg` / `render_mermaid_png` | `diagram_render`，`engine=mermaid` |
| `compile_plantuml` | `diagram_compile`，`engine=plantuml` |
| `render_plantuml_svg` / `render_plantuml_png` | `diagram_render`，`engine=plantuml` |

## 错误如何被感知

失败载荷至少包含：

```json
{
  "ok": false,
  "engine": "plantuml",
  "repairable": true,
  "line": 3,
  "column": null,
  "excerpt": "> 3: this is garbage $$$",
  "diagnostics": ["Error line 3 in file: diagram.puml"],
  "hint": "plantuml rejected line 3. Edit that line in the source, then call the same tool again with the corrected source."
}
```

`repairable: true` 表示源码可以改。缺 Java、缺 jar、缺 Node 或渲染超时是 `repairable: false`。

PlantUML 退出码不是 0，或者 SVG 里出现 `Syntax Error`，都算失败。错误图不会当作 `output_path` 返回。只跑 `--check-syntax` 不够，因为有些语法问题仍会以退出码 0 画进 SVG。

Mermaid 使用 `securityLevel: strict`。解析错误来自 `mermaid.parse` / `mermaid.render` 的行号和原文摘录。

## Excalidraw

`scene` 可以是：

- 完整文档：`{"type":"excalidraw","elements":[...]}`
- 元素数组：`[{...}]`
- 简单图：`{"nodes":[{"id":"a","label":"Cast","shape":"rectangle"}],"edges":[{"from":"a","to":"b"}]}`

支持 `rectangle`、`ellipse`、`diamond`、`text`、`line`、`arrow`、`freedraw`。`image` 只画占位框，不抓取远程地址。简单图按三列布局，箭头从节点右侧中点指向下一个节点左侧中点。SVG 由 roughjs 在本地生成；PNG 再用 Chromium 截图。

## 检查

```bash
python3 -m unittest discover -s tests
```

## 说明

PlantUML 在本机执行 jar。源码里的 `!include` 会按 PlantUML 自己的规则读本地文件，只应把这个服务暴露给可信的 agent。
