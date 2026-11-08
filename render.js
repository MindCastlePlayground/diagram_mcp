import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { JSDOM } from "jsdom";
import rough from "roughjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const NS = "http://www.w3.org/2000/svg";
const THEMES = new Set(["default", "base", "dark", "forest", "neutral"]);

function reply(payload) {
  process.stdout.write(JSON.stringify(payload));
}

function packError(error) {
  const hash = error && typeof error === "object" ? error.hash || null : null;
  const loc = hash && hash.loc ? hash.loc : null;
  let expected = null;
  if (hash && Array.isArray(hash.expected)) {
    expected = hash.expected.map((item) => String(item)).slice(0, 12);
  }
  const message = error && (error.str || error.message)
    ? String(error.str || error.message)
    : String(error);
  return {
    message,
    line: loc && Number.isFinite(loc.first_line) ? loc.first_line : null,
    column: loc && Number.isFinite(loc.first_column) ? loc.first_column : null,
    hashLine: hash && Number.isFinite(hash.line) ? hash.line : null,
    token: hash && hash.token != null ? String(hash.token) : null,
    expected,
  };
}

function bundle() {
  return path.join(root, "node_modules", "mermaid", "dist", "mermaid.min.js");
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString("utf8").trim();
  if (!text) throw new Error("renderer received an empty request");
  return JSON.parse(text);
}

class MermaidPage {
  constructor(payload) {
    this.payload = payload;
    this.browser = null;
    this.page = null;
  }

  async open() {
    const theme = this.payload.theme || "default";
    if (!THEMES.has(theme)) {
      throw new Error(`theme must be one of ${[...THEMES].join(", ")}`);
    }
    this.browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    this.page = await this.browser.newPage({
      viewport: { width: 1400, height: 900 },
      deviceScaleFactor: 1,
    });
    await this.page.setContent(
      "<!doctype html><html><head><meta charset=\"utf-8\"></head><body style=\"margin:0;background:#fff\"><div id=\"host\"></div></body></html>",
    );
    const background = this.payload.background || "white";
    const valid = await this.page.evaluate((value) => CSS.supports("background-color", value), background);
    if (!valid) throw new Error("background must be a valid CSS color");
    await this.page.evaluate((value) => {
      document.body.style.backgroundColor = value;
      document.documentElement.style.backgroundColor = value;
    }, background);
    await this.page.addScriptTag({ path: bundle() });
    await this.page.evaluate((chosen) => {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: chosen,
      });
    }, theme);
  }

  async close() {
    if (this.browser) await this.browser.close();
  }

  async evaluate(source, draw) {
    return this.page.evaluate(async ({ code, shouldDraw }) => {
      function pack(error) {
        const hash = error && typeof error === "object" ? error.hash || null : null;
        const loc = hash && hash.loc ? hash.loc : null;
        let expected = null;
        if (hash && Array.isArray(hash.expected)) {
          expected = hash.expected.map((item) => String(item)).slice(0, 12);
        }
        return {
          ok: false,
          message: error && (error.str || error.message) ? String(error.str || error.message) : String(error),
          line: loc && Number.isFinite(loc.first_line) ? loc.first_line : null,
          column: loc && Number.isFinite(loc.first_column) ? loc.first_column : null,
          hashLine: hash && Number.isFinite(hash.line) ? hash.line : null,
          token: hash && hash.token != null ? String(hash.token) : null,
          expected,
        };
      }
      try {
        await window.mermaid.parse(code);
        const type = window.mermaid.detectType ? window.mermaid.detectType(code) : null;
        if (!shouldDraw) return { ok: true, type };
        const rendered = await window.mermaid.render("diagram_mcp_graph", code);
        const host = document.getElementById("host");
        host.innerHTML = rendered.svg;
        return { ok: true, type, svg: rendered.svg };
      } catch (error) {
        return pack(error);
      }
    }, { code: source, shouldDraw: draw });
  }

  async write(meta) {
    const out = path.resolve(String(this.payload.output));
    fs.mkdirSync(path.dirname(out), { recursive: true });
    if (this.payload.format === "png") {
      const host = await this.page.locator("#host").boundingBox();
      if (!host || host.width < 1 || host.height < 1) {
        throw new Error("mermaid produced an empty canvas");
      }
      await this.page.screenshot({
        path: out,
        type: "png",
        clip: host,
        omitBackground: false,
      });
    } else {
      fs.writeFileSync(out, meta.svg, "utf8");
    }
    return {
      ok: true,
      type: meta.type || null,
      output: out,
      bytes: fs.statSync(out).size,
    };
  }
}

function num(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function elementsOf(scene) {
  if (Array.isArray(scene)) return { elements: scene, warnings: [] };
  if (scene && Array.isArray(scene.elements)) return { elements: scene.elements, warnings: [] };
  if (scene && Array.isArray(scene.nodes)) return graph(scene);
  throw new Error("scene must be an elements array, an Excalidraw document, or {nodes, edges}");
}

function graph(scene) {
  const warnings = [];
  const nodes = scene.nodes;
  const edges = Array.isArray(scene.edges) ? scene.edges : [];
  const cols = 3;
  const cellW = 240;
  const cellH = 170;
  const nodeW = 180;
  const nodeH = 80;
  const pos = new Map();
  const elements = [];
  nodes.forEach((node, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const x = 40 + col * cellW;
    const y = 40 + row * cellH;
    const id = node.id != null ? String(node.id) : `n${index}`;
    pos.set(id, { x, y, w: nodeW, h: nodeH });
    elements.push({
      type: node.shape || "rectangle",
      x,
      y,
      width: nodeW,
      height: nodeH,
      strokeColor: node.strokeColor || "#1e1e1e",
      backgroundColor: node.backgroundColor || "#fff8e7",
      fillStyle: node.fillStyle || "hachure",
      roughness: node.roughness ?? 1,
      seed: index + 1,
      strokeWidth: node.strokeWidth ?? 1.5,
      label: node.label || node.text || id,
    });
  });
  edges.forEach((edge, index) => {
    const from = pos.get(String(edge.from));
    const to = pos.get(String(edge.to));
    if (!from || !to) {
      warnings.push(`edge ${edge.from} -> ${edge.to} was skipped because a node is missing`);
      return;
    }
    const x = from.x + from.w;
    const y = from.y + from.h / 2;
    elements.push({
      type: "arrow",
      x,
      y,
      points: [[0, 0], [to.x - x, (to.y + to.h / 2) - y]],
      strokeColor: edge.strokeColor || "#1e1e1e",
      roughness: 1,
      seed: 1000 + index,
      strokeWidth: 1.5,
      label: edge.label || "",
    });
  });
  return { elements, warnings };
}

function optionsOf(el) {
  const fill = el.backgroundColor && el.backgroundColor !== "transparent" ? el.backgroundColor : undefined;
  return {
    stroke: el.strokeColor || "#1e1e1e",
    fill,
    fillStyle: el.fillStyle || "hachure",
    roughness: num(el.roughness, 1),
    seed: num(el.seed, 1),
    strokeWidth: num(el.strokeWidth, 1.5),
  };
}

function textOf(el) {
  return el.label || el.text || el.originalText || el.rawText || "";
}

function addText(document, svg, x, y, value, size, color) {
  if (!value) return;
  const node = document.createElementNS(NS, "text");
  node.setAttribute("x", String(x));
  node.setAttribute("y", String(y));
  node.setAttribute("text-anchor", "middle");
  node.setAttribute("dominant-baseline", "middle");
  node.setAttribute("font-family", "sans-serif");
  node.setAttribute("font-size", String(size || 16));
  node.setAttribute("fill", color || "#1e1e1e");
  node.textContent = String(value);
  svg.appendChild(node);
}

function arrowHead(document, svg, x1, y1, x2, y2, color) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const size = 12;
  const left = [x2 + Math.cos(angle + Math.PI * 0.82) * size, y2 + Math.sin(angle + Math.PI * 0.82) * size];
  const right = [x2 + Math.cos(angle - Math.PI * 0.82) * size, y2 + Math.sin(angle - Math.PI * 0.82) * size];
  const poly = document.createElementNS(NS, "polygon");
  poly.setAttribute("points", `${x2},${y2} ${left[0]},${left[1]} ${right[0]},${right[1]}`);
  poly.setAttribute("fill", color || "#1e1e1e");
  svg.appendChild(poly);
}

function pointsOf(el) {
  const x = num(el.x, 0);
  const y = num(el.y, 0);
  const raw = Array.isArray(el.points) ? el.points : [[0, 0]];
  return raw.map((point) => [x + num(point[0], 0), y + num(point[1], 0)]);
}

function drawElement(rc, document, svg, el) {
  const type = String(el.type || "rectangle");
  const x = num(el.x, 0);
  const y = num(el.y, 0);
  const w = num(el.width, 120);
  const h = num(el.height, 60);
  const style = optionsOf(el);
  if (type === "ellipse") {
    svg.appendChild(rc.ellipse(x + w / 2, y + h / 2, w, h, style));
    addText(document, svg, x + w / 2, y + h / 2, textOf(el), el.fontSize, el.strokeColor);
    return;
  }
  if (type === "diamond") {
    const pts = [[x + w / 2, y], [x + w, y + h / 2], [x + w / 2, y + h], [x, y + h / 2]];
    svg.appendChild(rc.polygon(pts, style));
    addText(document, svg, x + w / 2, y + h / 2, textOf(el), el.fontSize, el.strokeColor);
    return;
  }
  if (type === "line" || type === "arrow" || type === "freedraw") {
    const pts = pointsOf(el);
    if (pts.length >= 2) {
      svg.appendChild(type === "freedraw" ? rc.curve(pts, style) : rc.linearPath(pts, style));
      if (type === "arrow") {
        const end = pts[pts.length - 1];
        const prev = pts[pts.length - 2];
        arrowHead(document, svg, prev[0], prev[1], end[0], end[1], style.stroke);
      }
      const mid = pts[Math.floor(pts.length / 2)];
      addText(document, svg, mid[0], mid[1] - 10, textOf(el), el.fontSize, el.strokeColor);
    }
    return;
  }
  if (type === "text") {
    addText(document, svg, x, y, textOf(el), el.fontSize || 20, el.strokeColor);
    return;
  }
  if (type === "image") {
    svg.appendChild(rc.rectangle(x, y, w, h, style));
    addText(document, svg, x + w / 2, y + h / 2, textOf(el) || "image", el.fontSize, el.strokeColor);
    return;
  }
  svg.appendChild(rc.rectangle(x, y, Math.max(w, 1), Math.max(h, 1), style));
  addText(document, svg, x + w / 2, y + h / 2, textOf(el), el.fontSize, el.strokeColor);
}

function bounds(elements) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const el of elements) {
    const x = num(el.x, 0);
    const y = num(el.y, 0);
    const w = num(el.width, 0);
    const h = num(el.height, 0);
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + w);
    maxY = Math.max(maxY, y + h);
    for (const point of pointsOf(el)) {
      minX = Math.min(minX, point[0]);
      minY = Math.min(minY, point[1]);
      maxX = Math.max(maxX, point[0]);
      maxY = Math.max(maxY, point[1]);
    }
  }
  if (!Number.isFinite(minX)) return { x: 0, y: 0, w: 400, h: 240 };
  const pad = 28;
  return {
    x: minX - pad,
    y: minY - pad,
    w: Math.max(32, maxX - minX + pad * 2),
    h: Math.max(32, maxY - minY + pad * 2),
  };
}

function drawScene(scene) {
  const { elements, warnings } = elementsOf(scene);
  if (!elements.length) throw new Error("scene has no elements to draw");
  if (elements.length > 5000) throw new Error("scene exceeds 5000 elements");
  const dom = new JSDOM("<!doctype html><body></body>");
  const document = dom.window.document;
  const svg = document.createElementNS(NS, "svg");
  document.body.appendChild(svg);
  const box = bounds(elements);
  svg.setAttribute("xmlns", NS);
  svg.setAttribute("width", String(Math.ceil(box.w)));
  svg.setAttribute("height", String(Math.ceil(box.h)));
  svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
  const rc = rough.svg(svg);
  for (const el of elements) drawElement(rc, document, svg, el);
  return { svg: svg.outerHTML, warnings, count: elements.length, width: box.w, height: box.h };
}

async function writePng(svg, output, width, height) {
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage({
      viewport: {
        width: Math.max(64, Math.ceil(width)),
        height: Math.max(64, Math.ceil(height)),
      },
      deviceScaleFactor: 1,
    });
    await page.setContent(
      `<!doctype html><html><body style="margin:0;background:#fff">${svg}</body></html>`,
    );
    const box = await page.locator("svg").boundingBox();
    await page.screenshot({
      path: output,
      type: "png",
      clip: box || undefined,
      omitBackground: false,
    });
  } finally {
    await browser.close();
  }
}

async function renderExcalidraw(payload) {
  let drawn;
  try {
    drawn = drawScene(payload.scene);
  } catch (error) {
    return { ok: false, message: error.message || String(error) };
  }
  if (!payload.output) {
    return { ok: true, elements: drawn.count, warnings: drawn.warnings };
  }
  const out = path.resolve(String(payload.output));
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (payload.format === "png") {
    await writePng(drawn.svg, out, drawn.width, drawn.height);
  } else {
    fs.writeFileSync(out, drawn.svg, "utf8");
  }
  return {
    ok: true,
    output: out,
    bytes: fs.statSync(out).size,
    elements: drawn.count,
    warnings: drawn.warnings,
  };
}

async function renderMermaid(payload) {
  const page = new MermaidPage(payload);
  try {
    await page.open();
    const draw = payload.action !== "compile";
    const meta = await page.evaluate(String(payload.source || ""), draw);
    if (!meta.ok) return meta;
    if (!draw) return { ok: true, type: meta.type || null };
    return await page.write(meta);
  } finally {
    await page.close();
  }
}

async function main() {
  const payload = await readStdin();
  if (payload.action === "excalidraw") {
    reply(await renderExcalidraw(payload));
    return;
  }
  if (payload.action === "mermaid" || payload.action === "compile") {
    reply(await renderMermaid(payload));
    return;
  }
  reply({ ok: false, message: `unknown renderer action ${payload.action}` });
}

main().catch((error) => {
  reply({ ok: false, message: packError(error).message });
});
