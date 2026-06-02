#!/usr/bin/env python3
"""Simple HTTP server that serves the D3 graph viewer and provides a graph API.

Endpoints:
  GET /                                                    → D3 viewer (HTML)
  GET /api/graph?year=&month=&day=&refresh=1               → NDJSON stream with progress

Query params:
  year, month, day   — date to build (default: latest available)
  min_entity         — entity helper threshold (default: 3)
  ignore             — comma-separated articles to exclude
  user_agent         — custom User-Agent string
  refresh            — set to 1 to clear cache before building
"""
import json
import os
import shutil
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from wikigraph import build_graph, latest_available_date
from wikigraph.config import CACHE_DIR


VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>wikigraph viewer</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #1a1a2e; color: #e0e0e0; overflow: hidden; height: 100vh; }
#info {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: rgba(26,26,46,0.95); backdrop-filter: blur(10px);
  padding: 8px 16px; border-bottom: 1px solid #333;
  display: flex; align-items: center; gap: 12px; font-size: 12px; height: 42px; flex-wrap: wrap;
}
#info h1 { font-size: 14px; font-weight: 700; color: #fff; }
#info .stats { color: #888; }
#info input[type=text] { background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  padding: 2px 8px; border-radius: 4px; font-size: 12px; width: 140px; outline: none; }
#info input:focus { border-color: #6c5ce7; }
.ctrl { font-size: 11px; color: #aaa; display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.ctrl input[type=checkbox] { accent-color: #6c5ce7; }
.ctrl input[type=range] { width: 60px; height: 3px; accent-color: #6c5ce7; }
.ctrl select { background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  border-radius: 4px; font-size: 11px; padding: 1px 4px; outline: none; }
#progress {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%);
  background: rgba(0,0,0,0.85); color: #eee; padding: 24px 32px;
  border-radius: 8px; z-index: 300; text-align: center; display: none;
  border: 1px solid #555; max-width: 400px;
}
#progress .spinner { display: inline-block; width: 24px; height: 24px; border: 3px solid #444;
  border-top-color: #6c5ce7; border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 12px; }
@keyframes spin { to { transform: rotate(360deg); } }
#progress .msg { font-size: 13px; color: #ccc; }
#graph { position: fixed; top: 42px; left: 0; right: 0; bottom: 0; }
.link { stroke-opacity: 0.3; }
.link.wikilink { stroke: #6c5ce7; }
.link.category { stroke: #00b894; }
.link.entity { stroke: #fdcb6e; }
.node { cursor: pointer; }
.node image { clip-path: url(#round-clip); }
.node text { font-size: 10px; pointer-events: none; fill: #ccc;
             text-shadow: 0 1px 2px rgba(0,0,0,0.8); }
.node.helper circle { stroke: #666; stroke-width: 1px; stroke-dasharray: 3,2; fill-opacity: 0.6; }
.node.helper text { font-size: 9px; fill: #999; }
#tooltip {
  position: fixed; background: rgba(0,0,0,0.85); color: #eee; padding: 6px 10px;
  border-radius: 6px; font-size: 11px; pointer-events: none; z-index: 200;
  max-width: 280px; display: none; border: 1px solid #555;
}
#side-panel {
  position: fixed; top: 42px; right: -400px; width: 380px; bottom: 0;
  background: rgba(30,30,50,0.97); backdrop-filter: blur(10px);
  border-left: 1px solid #444; z-index: 99; transition: right 0.3s ease;
  overflow-y: auto; padding: 20px;
}
#side-panel.open { right: 0; }
#side-panel .close { float: right; cursor: pointer; font-size: 20px; color: #888; }
#side-panel .close:hover { color: #fff; }
#side-panel h2 { font-size: 16px; margin-bottom: 4px; color: #fff; }
#side-panel .meta { font-size: 12px; color: #888; margin-bottom: 10px; }
#side-panel .cluster-tag {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 600; margin-bottom: 10px;
}
#side-panel img { max-width: 100%; border-radius: 6px; margin-bottom: 10px; }
#side-panel .summary { font-size: 13px; line-height: 1.5; color: #ccc; margin-bottom: 10px; }
#side-panel .connections h3 { font-size: 13px; color: #aaa; margin-bottom: 6px; }
#side-panel .connections ul { list-style: none; font-size: 12px; }
#side-panel .connections li { padding: 2px 0; color: #888; cursor: pointer; }
#side-panel .connections li:hover { color: #ccc; }
#side-panel a.ext-link { color: #6c5ce7; text-decoration: none; font-size: 13px; display: inline-block; margin-top: 8px; }
#side-panel a.ext-link:hover { text-decoration: underline; }
</style>
</head>
<body>
<div id="progress">
  <div class="spinner"></div>
  <div class="msg" id="progress-msg">Loading graph data...</div>
</div>
<div id="info">
  <h1>wikigraph</h1>
  <span class="stats" id="stats"></span>
  <span style="flex:1"></span>
  <label class="ctrl">Date <select id="date-preset"></select></label>
  <button id="build-btn" style="background:#6c5ce7;border:none;color:#fff;border-radius:4px;padding:2px 10px;font-size:11px;cursor:pointer;">Build</button>
  <label class="ctrl"><input type="checkbox" id="toggle-helpers" checked> Helpers</label>
  <label class="ctrl">Spacing <input type="range" id="spacing" min="0" max="100" value="27"></label>
  <input type="text" id="search" placeholder="Search...">
</div>
<svg id="graph">
  <defs><clipPath id="round-clip"><circle r="25"/></clipPath></defs>
</svg>
<div id="tooltip"></div>
<div id="side-panel">
  <span class="close" onclick="closePanel()">✕</span>
  <div id="panel-content"><p style="color:#666;padding:20px;text-align:center;">Click a node to see details</p></div>
</div>
<script>
const edgeColors = { wikilink: "#6c5ce7", category: "#00b894", entity: "#fdcb6e" };
let nodes = [], links = [], meta = {}, nodeMap = {}, simulation;

// Populate date dropdown with recent dates
(function() {
  const sel = document.getElementById("date-preset");
  const d = new Date();
  for (let i = 0; i < 14; i++) {
    const dt = new Date(d);
    dt.setDate(dt.getDate() - i);
    const y = dt.getFullYear(), m = dt.getMonth() + 1, dd = dt.getDate();
    const label = `${y}-${String(m).padStart(2,'0')}-${String(dd).padStart(2,'0')}`;
    const opt = document.createElement("option");
    opt.value = `${y}/${m}/${dd}`;
    opt.textContent = label;
    if (i === 0) opt.selected = true;
    sel.appendChild(opt);
  }
})();

document.getElementById("build-btn").addEventListener("click", () => {
  const val = document.getElementById("date-preset").value;
  const parts = val.split("/");
  loadGraph(parts[0], parts[1], parts[2]);
});

function loadGraph(year, month, day) {
  const progress = document.getElementById("progress");
  const msgEl = document.getElementById("progress-msg");
  progress.style.display = "block";
  msgEl.textContent = "Connecting to server...";

  const url = `/api/graph?year=${year}&month=${month}&day=${day}`;
  fetch(url).then(async resp => {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          if (msg.type === "progress") {
            msgEl.textContent = msg.message;
          } else if (msg.type === "graph") {
            progress.style.display = "none";
            renderGraph(msg.data);
          } else if (msg.type === "error") {
            progress.style.display = "none";
            msgEl.textContent = "Error: " + msg.message;
            progress.style.display = "block";
          }
        } catch(e) {}
      }
    }
  }).catch(err => {
    msgEl.textContent = "Network error: " + err.message;
  });
}

function renderGraph(data) {
  meta = data.meta;
  nodes = data.nodes.map(d => ({ ...d }));
  links = data.links.map(d => ({ ...d }));
  nodeMap = {};
  nodes.forEach(n => nodeMap[n.id] = n);

  document.getElementById("stats").textContent =
    `${meta.total_articles} articles · ${meta.total_nodes} nodes · ${meta.total_edges} connections`;

  // Clear existing
  d3.select("#graph").select("g.container").remove();

  const svg = d3.select("#graph");
  function resizeSVG() { svg.attr("width", window.innerWidth).attr("height", window.innerHeight - 42); }
  resizeSVG();
  window.addEventListener("resize", resizeSVG);
  const container = svg.append("g").attr("class", "container");

  function getCenter() {
    const el = document.getElementById("graph");
    const w = el.clientWidth || window.innerWidth || 1280;
    const h = el.clientHeight || window.innerHeight - 42 || 720;
    return [Math.max(w / 2, 400), Math.max(h / 2, 300)];
  }

  const zoom = d3.zoom().scaleExtent([0.1, 8]).on("zoom", event => {
    container.attr("transform", event.transform);
  });
  svg.call(zoom);

  function getCharge() {
    const el = document.getElementById("graph");
    const w = el.clientWidth || window.innerWidth || 1280;
    const h = el.clientHeight || window.innerHeight - 42 || 720;
    const spacingVal = parseInt(document.getElementById("spacing").value) || 27;
    const mult = 0.2 + (spacingVal / 100) * 2.96;
    return -Math.sqrt(w * h) * 0.31 * mult;
  }

  simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id)
      .distance(d => d.type === "wikilink" ? 120 : 90)
      .strength(d => d.type === "wikilink" ? 0.5 : 0.2))
    .force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()))
    .force("center", d3.forceCenter(...getCenter()).strength(0.03))
    .force("collide", d3.forceCollide(d => d.type === "helper" ? 12 : Math.min(d.size || 22, 34) + 10))
    .alphaDecay(0.002)
    .on("tick", ticked);

  let showHelpers = true;
  document.getElementById("toggle-helpers").onchange = function() {
    showHelpers = this.checked;
    node.style("display", d => (d.type === "helper" && !showHelpers) ? "none" : null);
    link.style("display", l => showHelpers ? null : (l.type === "category" || l.type === "entity") ? "none" : null);
  };

  document.getElementById("spacing").oninput = function() {
    simulation.force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()));
    simulation.alpha(0.3).restart();
  };

  nodes.forEach(d => {
    const [cx, cy] = getCenter();
    d.x = cx + (Math.random() - 0.5) * (getCenter()[0] * 1.2);
    d.y = cy + (Math.random() - 0.5) * (getCenter()[1] * 1.2);
  });

  window.addEventListener("resize", () => {
    simulation.force("center", d3.forceCenter(...getCenter()).strength(0.03));
    simulation.force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()));
    simulation.alpha(0.3).restart();
  });

  const link = container.append("g").selectAll("line")
    .data(links).join("line")
    .attr("class", d => `link ${d.type}`)
    .attr("stroke-width", d => Math.max(0.5, Math.min(3, d.weight)))
    .attr("stroke", d => edgeColors[d.type] || "#555");

  const node = container.append("g").selectAll("g.node")
    .data(nodes).join("g")
    .attr("class", d => `node ${d.type}`)
    .call(d3.drag()
      .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  node.each(function(d) {
    const g = d3.select(this);
    if (d.type === "helper") {
      g.append("circle").attr("r", 5).attr("fill", d.color || "#b0b0b0")
        .attr("stroke", "#666").attr("stroke-width", 1).attr("stroke-dasharray", "3,2").attr("fill-opacity", 0.6);
      g.append("text").attr("dx", 8).attr("dy", 3).style("font-size", "10px")
        .text((d.label || "").length > 25 ? (d.label || "").slice(0, 24) + "\u2026" : (d.label || ""));
    } else {
      const r = Math.min(d.size || 12, 25);
      g.append("circle").attr("r", r).attr("fill", "none").attr("stroke", d.color || "#6c5ce7").attr("stroke-width", 2).attr("opacity", 0.8);
      g.append("circle").attr("r", r-1).attr("fill", d.color || "#6c5ce7").attr("fill-opacity", 0.3);
      const imgUrl = d.image_url || d.page_image_url;
      if (imgUrl && !imgUrl.includes("W.svg")) {
        const img = new Image();
        img.onload = () => { g.append("image").attr("xlink:href", imgUrl).attr("x", -r).attr("y", -r).attr("width", r*2).attr("height", r*2).attr("clip-path", "url(#round-clip)"); };
        img.src = imgUrl;
      }
      g.append("text").attr("dx", 0).attr("dy", r + 12).attr("text-anchor", "middle").style("font-size", "10px")
        .text((d.title || "").length > 20 ? (d.title || "").slice(0, 19) + "\u2026" : (d.title || ""));
    }
  });

  node.on("mouseover", function(event, d) {
    const connected = new Set([d.id]);
    data.links.forEach(l => {
      const sid = l.source.id || l.source;
      const tid = l.target.id || l.target;
      if (sid === d.id) connected.add(tid);
      if (tid === d.id) connected.add(sid);
    });
    node.style("opacity", n => connected.has(n.id) ? 1 : 0.15);
    link.style("opacity", l => {
      const sid = l.source.id || l.source;
      const tid = l.target.id || l.target;
      return sid === d.id || tid === d.id ? 1 : 0.04;
    });
    const tip = document.getElementById("tooltip");
    tip.style.display = "block";
    tip.style.left = (event.pageX + 12) + "px";
    tip.style.top = (event.pageY - 10) + "px";
    if (d.type === "article") {
      tip.innerHTML = `<strong>${escHtml(d.title)}</strong><br>${d.cluster || ""} ${d.views ? "· " + fmtViews(d.views) + " views" : ""}`;
    } else {
      tip.innerHTML = `<strong>${escHtml(d.label)}</strong> (${d.helper_type})<br>Connected to ${connected.size - 1} articles`;
    }
  }).on("mouseout", function() {
    node.style("opacity", 1);
    link.style("opacity", 0.3);
    document.getElementById("tooltip").style.display = "none";
  }).on("click", function(event, d) {
    event.stopPropagation();
    clickNode(d, data);
  });

  function ticked() {
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  }

  document.getElementById("search").oninput = function() {
    const q = this.value.toLowerCase().trim();
    node.style("opacity", function(d) {
      const name = (d.title || d.label || "").toLowerCase();
      return !q || name.includes(q) ? 1 : 0.1;
    });
    link.style("opacity", function(l) {
      if (!q) return 0.3;
      const sn = nodeMap[l.source.id || l.source];
      const tn = nodeMap[l.target.id || l.target];
      const sm = sn && (sn.title || sn.label || "").toLowerCase().includes(q);
      const tm = tn && (tn.title || tn.label || "").toLowerCase().includes(q);
      return (sm || tm) ? 0.3 : 0.03;
    });
  };

  svg.on("click", () => closePanel());
}

function clickNode(d, data) {
  document.getElementById("tooltip").style.display = "none";
  const panel = document.getElementById("side-panel");
  const content = document.getElementById("panel-content");
  const connected = [];
  const seen = new Set();
  data.links.forEach(l => {
    const sid = l.source.id || l.source, tid = l.target.id || l.target;
    if (sid === d.id && data.nodes.find(n => n.id === tid && n.type === "article")) {
      if (!seen.has(tid)) { seen.add(tid); connected.push({ id: tid, type: l.type }); }
    }
    if (tid === d.id && data.nodes.find(n => n.id === sid && n.type === "article")) {
      if (!seen.has(sid)) { seen.add(sid); connected.push({ id: sid, type: l.type }); }
    }
  });
  const edgeIcon = { wikilink: "\uD83D\uDD17", category: "\uD83D\uDCC1", entity: "\uD83D\uDD24" };
  let html = "";
  if (d.type === "helper") {
    const label = d.label || d.id.replace(/^(cat:|ent:)/, "");
    const htype = d.helper_type === "category" ? "Shared Category" : "Shared Entity";
    const wikiUrl = d.helper_type === "category"
      ? `https://en.wikipedia.org/wiki/Category:${encodeURIComponent(label.replace(/ /g, "_"))}`
      : `https://en.wikipedia.org/wiki/${encodeURIComponent(label.replace(/ /g, "_"))}`;
    html += `<h2>${escHtml(label)}</h2><div class="meta">${htype}</div>`;
    html += `<div class="connections"><h3>Connected articles (${connected.length})</h3><ul>`;
    connected.forEach(c => {
      const cn = data.nodes.find(n => n.id === c.id);
      html += `<li onclick="clickNode(nodeMap['${c.id}'], window._graphData)">${edgeIcon[c.type] || "•"} ${escHtml(cn ? cn.title || cn.label : c.id)}</li>`;
    });
    html += `</ul></div><a class="ext-link" href="${wikiUrl}" target="_blank">Open on Wikipedia →</a>`;
  } else {
    const color = d.color || "#6c5ce7";
    html += `<h2>${escHtml(d.title)}</h2>`;
    if (d.rank) html += `<div class="meta">#${d.rank} · ${fmtViews(d.views)} views</div>`;
    if (d.cluster) html += `<div class="cluster-tag" style="background:${color}44;color:${color}">${d.cluster}</div>`;
    const imgUrl = d.image_url || d.page_image_url;
    if (imgUrl && !imgUrl.includes("W.svg")) html += `<img src="${escHtml(imgUrl)}" alt="${escHtml(d.title)}" onerror="this.style.display='none'">`;
    const blurb = d.summary || d.extract;
    if (blurb) html += `<div class="summary">${escHtml(blurb)}</div>`;
    if (connected.length > 0) {
      html += `<div class="connections"><h3>Connected (${connected.length})</h3><ul>`;
      connected.forEach(c => {
        const cn = data.nodes.find(n => n.id === c.id);
        html += `<li onclick="clickNode(nodeMap['${c.id}'], window._graphData)">${edgeIcon[c.type] || "•"} ${escHtml(cn ? cn.title || cn.label : c.id)}</li>`;
      });
      html += `</ul></div>`;
    }
    html += `<a class="ext-link" href="${d.url || 'https://en.wikipedia.org/wiki/' + d.id}" target="_blank">Open on Wikipedia →</a>`;
  }
  content.innerHTML = html;
  panel.classList.add("open");
}

function closePanel() { document.getElementById("side-panel").classList.remove("open"); }
function escHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function fmtViews(v) {
  if (!v) return "";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toString();
}

// Auto-load latest date on page load
(function() {
  const sel = document.getElementById("date-preset");
  if (sel.options.length > 0) {
    const val = sel.options[0].value.split("/");
    // Store graphData globally for side-panel links
    window._graphData = null;
    (function attach() {
      const orig = clickNode;
      window.clickNode = function(d) { orig(d, window._graphData || { nodes, links }); };
    })();
    loadGraph(val[0], val[1], val[2]);
  }
})();
</script>
</body>
</html>"""


class GraphAPIHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/graph":
            params = parse_qs(parsed.query)
            try:
                year = params.get("year", [None])[0]
                month = params.get("month", [None])[0]
                day = params.get("day", [None])[0]
                if not (year and month and day):
                    ly, lm, ld = latest_available_date()
                    year = year or ly
                    month = month or lm
                    day = day or ld
                min_entity = int(params.get("min_entity", ["3"])[0])
                ignore_raw = params.get("ignore", [None])[0]
                ignore_list = ignore_raw.split(",") if ignore_raw else None
                user_agent = params.get("user_agent", [None])[0]
                refresh = params.get("refresh", ["0"])[0] == "1"
            except (ValueError, KeyError):
                self.send_error(400, "Invalid parameters")
                return

            if refresh:
                if os.path.exists(CACHE_DIR):
                    shutil.rmtree(CACHE_DIR)
                    print("  Cache cleared on refresh request")

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            def write_json(obj):
                self.wfile.write((json.dumps(obj) + "\n").encode())
                self.wfile.flush()

            try:
                # Store for side-panel linkbacks
                write_json({"type": "progress", "message": "Fetching top 100..."})
                graph_data = build_graph(
                    year, month, day,
                    min_entity_share=min_entity,
                    ignore_articles=ignore_list,
                    progress_callback=lambda m: write_json({"type": "progress", "message": m}),
                    user_agent=user_agent,
                )
                write_json({"type": "graph", "data": graph_data})
            except Exception as e:
                write_json({"type": "error", "message": str(e)})
            return

        # Serve the viewer at /
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = VIEWER_HTML.encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        """Quiet logs except errors."""
        if args and "404" in str(args[0]):
            super().log_message(format, *args)


def main():
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) >= 2 else "8000"))
    server = HTTPServer(("0.0.0.0", port), GraphAPIHandler)
    print(f"wikigraph server at http://localhost:{port}")
    print(f"  Viewer: http://localhost:{port}")
    print(f"  API:    http://localhost:{port}/api/graph?year=2026&month=5&day=29")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
