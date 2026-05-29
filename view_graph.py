#!/usr/bin/env python3
"""Quick graph viewer — renders a wikigraph JSON file as an interactive
D3.js force-directed graph in the browser.

Usage:
    python view_graph.py graph.json
    python view_graph.py graph.json --port 8888
    python view_graph.py --date 2026 5 29          # build + view in one step

Dependencies: none beyond stdlib + what wikigraph already needs.
D3.js v7 is loaded from CDN — no install required.
"""
import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HTML_TEMPLATE = r"""<!DOCTYPE html>
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
  display: flex; align-items: center; gap: 12px; font-size: 12px; height: 36px;
}
#info h1 { font-size: 14px; font-weight: 700; color: #fff; }
#info .stats { color: #888; }
#info input { background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  padding: 2px 8px; border-radius: 4px; font-size: 12px; width: 160px; outline: none; }
#info input:focus { border-color: #6c5ce7; }
#graph { position: fixed; top: 36px; left: 0; right: 0; bottom: 0; }
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
.ctrl { font-size: 11px; color: #aaa; display: flex; align-items: center; gap: 4px; cursor: pointer; white-space: nowrap; }
.ctrl input[type=checkbox] { accent-color: #6c5ce7; }
.ctrl input[type=range] { width: 60px; height: 3px; accent-color: #6c5ce7; cursor: pointer; }

#side-panel {
  position: fixed; top: 36px; right: -400px; width: 380px; bottom: 0;
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
<div id="info">
  <h1>wikigraph viewer</h1>
  <span class="stats" id="stats"></span>
  <span style="flex:1"></span>
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
  <div id="panel-content"></div>
</div>
<script>
const GRAPH_DATA = __GRAPH_DATA__;

const edgeColors = { wikilink: "#6c5ce7", category: "#00b894", entity: "#fdcb6e" };

const nodes = GRAPH_DATA.nodes.map(d => ({ ...d }));
const links = GRAPH_DATA.links.map(d => ({ ...d }));
const nodeMap = {};
nodes.forEach(n => nodeMap[n.id] = n);

document.getElementById("stats").textContent =
  `${GRAPH_DATA.meta.total_articles} articles \u00b7 ${GRAPH_DATA.meta.total_nodes} nodes \u00b7 ${GRAPH_DATA.meta.total_edges} connections`;

const svg = d3.select("#graph");
// Set SVG dimensions to fill the viewport so D3's coordinate system
// matches the visual display, not the default 300x150 intrinsic size.
function resizeSVG() {
  svg.attr("width", window.innerWidth)
     .attr("height", window.innerHeight - 36);
}
resizeSVG();
window.addEventListener("resize", resizeSVG);
const container = svg.append("g").attr("class", "container");

// Use the SVG element's actual dimensions for the force center, not window.innerWidth/Height.
// Falls back to window dimensions if SVG hasn't been laid out yet.
function getCenter() {
  const box = document.getElementById("graph-container");
  if (box) {
    const r = box.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return [r.width / 2, r.height / 2];
  }
  const el = document.getElementById("graph");
  const w = el.clientWidth || window.innerWidth || 1280;
  const h = el.clientHeight || window.innerHeight - 36 || 720;
  return [Math.max(w / 2, 400), Math.max(h / 2, 300)];
}

const zoom = d3.zoom().scaleExtent([0.1, 8]).on("zoom", event => {
  container.attr("transform", event.transform);
});
svg.call(zoom);

// Compute force charge proportional to viewport area, scaled by the
// spacing slider (0-100). Default spacing=27 gives multiplier ≈ 1.0.
function getCharge() {
  const el = document.getElementById("graph");
  const w = el.clientWidth || window.innerWidth || 1280;
  const h = el.clientHeight || window.innerHeight - 36 || 720;
  const spacingVal = parseInt(document.getElementById("spacing").value) || 27;
  const mult = 0.2 + (spacingVal / 100) * 2.96;  // 0.2 at min, ~3.16 at max
  return -Math.sqrt(w * h) * 0.31 * mult;
}

const simulation = d3.forceSimulation(nodes)
  .force("link", d3.forceLink(links).id(d => d.id)
    .distance(d => d.type === "wikilink" ? 120 : 90)
    .strength(d => d.type === "wikilink" ? 0.5 : 0.2))
  .force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()))
  .force("center", d3.forceCenter(...getCenter()).strength(0.03))
  .force("collide", d3.forceCollide(d => d.type === "helper" ? 12 : Math.min(d.size || 22, 34) + 10))
  .alphaDecay(0.002)
  .on("tick", ticked);

// Helper node toggle
let showHelpers = true;
document.getElementById("toggle-helpers").addEventListener("change", function() {
  showHelpers = this.checked;
  node.style("display", d => (d.type === "helper" && !showHelpers) ? "none" : null);
  link.style("display", l => {
    if (showHelpers) return null;
    return (l.type === "category" || l.type === "entity") ? "none" : null;
  });
});

// Spacing slider
document.getElementById("spacing").addEventListener("input", function() {
  simulation.force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()));
  simulation.alpha(0.3).restart();
});

// Randomize initial positions proportional to viewport size
nodes.forEach(d => {
  const [cx, cy] = getCenter();
  d.x = cx + (Math.random() - 0.5) * (getCenter()[0] * 1.2);
  d.y = cy + (Math.random() - 0.5) * (getCenter()[1] * 1.2);
});

// Recenter and rescale on window resize
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
  GRAPH_DATA.links.forEach(l => {
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
    tip.innerHTML = `<strong>${d.title}</strong><br>${d.cluster || ""} \u00b7 ${d.views ? (d.views >= 1e6 ? (d.views/1e6).toFixed(1)+"M" : d.views >= 1e3 ? (d.views/1e3).toFixed(1)+"K" : d.views) : ""} views`;
  } else {
    tip.innerHTML = `<strong>${d.label}</strong> (${d.helper_type})<br>Connected to ${connected.size - 1} articles`;
  }
}).on("mouseout", function() {
  node.style("opacity", 1);
  link.style("opacity", 0.3);
  document.getElementById("tooltip").style.display = "none";
}).on("click", function(event, d) {
  event.stopPropagation();
  clickNode(d);
});

function clickNode(d) {
  document.getElementById("tooltip").style.display = "none";
  const panel = document.getElementById("side-panel");
  const content = document.getElementById("panel-content");

  // Gather connected articles with edge types
  const connected = [];
  const seen = new Set();
  GRAPH_DATA.links.forEach(l => {
    const sid = l.source.id || l.source;
    const tid = l.target.id || l.target;
    if (sid === d.id && GRAPH_DATA.nodes.find(n => n.id === tid && n.type === "article")) {
      if (!seen.has(tid)) { seen.add(tid); connected.push({ id: tid, type: l.type }); }
    }
    if (tid === d.id && GRAPH_DATA.nodes.find(n => n.id === sid && n.type === "article")) {
      if (!seen.has(sid)) { seen.add(sid); connected.push({ id: sid, type: l.type }); }
    }
  });

  let html = "";
  const edgeIcon = { wikilink: "\uD83D\uDD17", category: "\uD83D\uDCC1", entity: "\uD83D\uDD24" };

  if (d.type === "helper") {
    const label = d.label || d.id.replace(/^(cat:|ent:)/, "");
    const htype = d.helper_type === "category" ? "Shared Category" : "Shared Entity";
    const wikiUrl = d.helper_type === "category"
      ? `https://en.wikipedia.org/wiki/Category:${encodeURIComponent(label.replace(/ /g, "_"))}`
      : `https://en.wikipedia.org/wiki/${encodeURIComponent(label.replace(/ /g, "_"))}`;
    html += `<h2>${escHtml(label)}</h2>`;
    html += `<div class="meta">${htype}</div>`;
    html += `<div class="connections"><h3>Connected articles (${connected.length})</h3><ul>`;
    connected.forEach(c => {
      const cn = GRAPH_DATA.nodes.find(n => n.id === c.id);
      const name = cn ? cn.title || cn.label : c.id;
      html += `<li onclick="clickNode(nodeMap['${c.id}'])">${edgeIcon[c.type] || "\u2022"} ${escHtml(name)}</li>`;
    });
    html += `</ul></div>`;
    html += `<a class="ext-link" href="${wikiUrl}" target="_blank">Open on Wikipedia \u2192</a>`;
  } else {
    const color = d.color || "#6c5ce7";
    html += `<h2>${escHtml(d.title)}</h2>`;
    if (d.rank) html += `<div class="meta">#${d.rank} \u00b7 ${fmtViews(d.views)} views</div>`;
    if (d.cluster) html += `<div class="cluster-tag" style="background:${color}44;color:${color}">${d.cluster}</div>`;
    const imgUrl = d.image_url || d.page_image_url;
    if (imgUrl && !imgUrl.includes("W.svg")) {
      html += `<img src="${escHtml(imgUrl)}" alt="${escHtml(d.title)}" onerror="this.style.display='none'">`;
    }
    if (d.summary) html += `<div class="summary">${d.summary}</div>`;
    if (connected.length > 0) {
      html += `<div class="connections"><h3>Connected (${connected.length})</h3><ul>`;
      connected.forEach(c => {
        const cn = GRAPH_DATA.nodes.find(n => n.id === c.id);
        const name = cn ? cn.title || cn.label : c.id;
        html += `<li onclick="clickNode(nodeMap['${c.id}'])">${edgeIcon[c.type] || "\u2022"} ${escHtml(name)}</li>`;
      });
      html += `</ul></div>`;
    }
    html += `<a class="ext-link" href="${d.url || 'https://en.wikipedia.org/wiki/' + d.id}" target="_blank">Open on Wikipedia \u2192</a>`;
  }

  content.innerHTML = html;
  panel.classList.add("open");
}

function closePanel() {
  document.getElementById("side-panel").classList.remove("open");
}

// Close panel when clicking the graph background
svg.on("click", function() {
  closePanel();
});

function escHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function fmtViews(v) {
  if (!v) return "";
  if (v >= 1000000) return (v / 1000000).toFixed(1) + "M";
  if (v >= 1000) return (v / 1000).toFixed(1) + "K";
  return v.toString();
}

function ticked() {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${d.x},${d.y})`);
}

document.getElementById("search").addEventListener("input", function() {
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
});
</script>
</body>
</html>"""


class ViewerHandler(BaseHTTPRequestHandler):
    graph_json = ""

    def do_GET(self):
        if self.path == "/":
            html = HTML_TEMPLATE.replace("__GRAPH_DATA__", self.graph_json)
            data = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # quiet


def main():
    import argparse
    parser = argparse.ArgumentParser(description="View a wikigraph JSON file in the browser")
    parser.add_argument("file", nargs="?", help="Path to graph JSON file")
    parser.add_argument("--date", nargs=3, type=int, metavar=("YEAR", "MONTH", "DAY"),
                        help="Build graph for a specific date (no file needed)")
    parser.add_argument("--port", type=int, default=8765, help="Port to serve on (default: 8765)")
    args = parser.parse_args()

    if args.date:
        from wikigraph import build_graph
        year, month, day = args.date
        print(f"Building graph for {year}/{month}/{day}...")
        data = build_graph(year, month, day)
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        with open(path) as f:
            data = json.load(f)
    else:
        # Try to auto-find graph_data.json in current directory
        path = Path("graph_data.json")
        if path.exists():
            with open(path) as f:
                data = json.load(f)
        else:
            print("Usage: python view_graph.py <graph.json>")
            print("   or: python view_graph.py --date 2026 5 29")
            print("   or: python view_graph.py  (auto-finds graph_data.json)")
            sys.exit(1)

    ViewerHandler.graph_json = json.dumps(data)
    server = HTTPServer(("127.0.0.1", args.port), ViewerHandler)
    url = f"http://localhost:{args.port}"
    print(f"  {data['meta']['total_articles']} articles, {data['meta']['total_nodes']} nodes, {data['meta']['total_edges']} edges")
    print(f"  Opening {url} ...")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
