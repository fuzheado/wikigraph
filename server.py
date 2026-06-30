#!/usr/bin/env python3
"""HTTP server that serves the D3 graph viewer and provides graph APIs.

Endpoints:
  GET /                                                     → D3 viewer (HTML)
  GET /api/graph?year=&month=&day=&refresh=1                → NDJSON stream with progress (date mode)
  POST /api/graph-from-list                                 → NDJSON stream with progress (custom list)

Query params (GET /api/graph):
  year, month, day   — date to build (default: latest available)
  min_entity         — entity helper threshold (default: 3)
  ignore             — comma-separated articles to exclude
  user_agent         — custom User-Agent string
  refresh            — set to 1 to clear cache before building

POST body (POST /api/graph-from-list):
  {"titles": ["Article A", "Article B", ...]}
"""
import json
import os
import shutil
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from wikigraph import build_graph, build_graph_from_list, latest_available_date
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
  display: flex; align-items: center; gap: 12px; font-size: 12px; height: 42px;
}
#info h1 { font-size: 14px; font-weight: 700; color: #fff; margin-right: 4px; }
#info .stats { color: #888; font-size: 11px; }
#info input[type=text] { background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  padding: 2px 8px; border-radius: 4px; font-size: 12px; width: 140px; outline: none; }
#info input:focus { border-color: #6c5ce7; }
.ctrl { font-size: 11px; color: #aaa; display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.ctrl input[type=checkbox] { accent-color: #6c5ce7; }
.ctrl input[type=range] { width: 60px; height: 3px; accent-color: #6c5ce7; }

/* Mode tabs */
.mode-tabs { display: flex; gap: 2px; background: #2a2a4a; border-radius: 4px; padding: 2px; }
.mode-tab { background: none; border: none; color: #888; padding: 2px 10px;
  font-size: 11px; cursor: pointer; border-radius: 3px; transition: all 0.2s; }
.mode-tab.active { background: #6c5ce7; color: #fff; }
.mode-tab:hover:not(.active) { color: #ccc; }

/* Controls container — swapped based on mode */
#date-controls, #custom-controls { display: none; align-items: center; gap: 6px; }
#date-controls.active, #custom-controls.active { display: flex; }
#date-controls select { background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  border-radius: 4px; font-size: 11px; padding: 1px 4px; outline: none; }

.btn-primary { background:#6c5ce7; border:none; color:#fff; border-radius:4px;
  padding:2px 10px; font-size:11px; cursor:pointer; }
.btn-primary:hover { background:#7c6df7; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

/* Custom input panel */
#custom-panel {
  position: fixed; top: 42px; left: 0; right: 0; z-index: 90;
  background: rgba(26,26,46,0.98); backdrop-filter: blur(10px);
  border-bottom: 1px solid #333; padding: 12px 16px;
  display: none; gap: 10px; align-items: flex-start;
}
#custom-panel.open { display: flex; }
#custom-panel textarea {
  flex: 1; background: #2a2a4a; border: 1px solid #444; color: #e0e0e0;
  border-radius: 4px; padding: 8px; font-size: 12px; font-family: 'SF Mono', Monaco, monospace;
  resize: vertical; min-height: 120px; max-height: 300px; outline: none;
}
#custom-panel textarea:focus { border-color: #6c5ce7; }
#custom-panel .input-actions { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
#custom-panel .input-actions .hint { font-size: 10px; color: #666; line-height: 1.4; }
#custom-panel .input-actions .count { font-size: 11px; color: #888; }

/* Graph area */
#graph { position: fixed; top: 42px; left: 0; right: 0; bottom: 0; transition: top 0.15s; }

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

  <!-- Mode tabs -->
  <div class="mode-tabs">
    <button class="mode-tab active" data-mode="date" onclick="switchMode('date')">Top Articles</button>
    <button class="mode-tab" data-mode="custom" onclick="switchMode('custom')">Custom List</button>
  </div>

  <!-- Date mode controls -->
  <div id="date-controls" class="active">
    <select id="date-preset"></select>
    <button class="btn-primary" id="build-btn">Build</button>
  </div>

  <!-- Custom mode controls (minimal) -->
  <div id="custom-controls">
    <span id="article-count" class="ctrl"></span>
  </div>

  <label class="ctrl"><input type="checkbox" id="toggle-helpers" checked> Helpers</label>
  <label class="ctrl">Spacing <input type="range" id="spacing" min="0" max="100" value="27"></label>
  <input type="text" id="search" placeholder="Search...">
</div>

<!-- Custom list panel (below top bar) -->
<div id="custom-panel">
  <textarea id="article-list" placeholder="Enter one Wikipedia article title per line...

Example:
Artificial intelligence
Machine learning
Deep learning
Neural network
ChatGPT"></textarea>
  <div class="input-actions">
    <button class="btn-primary" id="build-custom-btn">Build Graph</button>
    <span class="hint">One article title per line.<br>Spaces or underscores OK.</span>
  </div>
</div>

<svg id="graph">
  <defs><clipPath id="round-clip"><circle r="25"/></clipPath></defs>
</svg>
<div id="tooltip"></div>
<div id="side-panel">
  <span class="close" onclick="closePanel()">&#x2715;</span>
  <div id="panel-content"><p style="color:#666;padding:20px;text-align:center;">Click a node to see details</p></div>
</div>
<script>
const edgeColors = { wikilink: "#6c5ce7", category: "#00b894", entity: "#fdcb6e" };
let nodes = [], links = [], meta = {}, nodeMap = {}, simulation;
let currentMode = "date";

// ─── Mode switching ─────────────────────────────────────────

function switchMode(mode) {
  currentMode = mode;
  document.querySelectorAll(".mode-tab").forEach(t => t.classList.toggle("active", t.dataset.mode === mode));
  document.getElementById("date-controls").classList.toggle("active", mode === "date");
  document.getElementById("custom-controls").classList.toggle("active", mode === "custom");
  document.getElementById("custom-panel").classList.toggle("open", mode === "custom");
  updateGraphLayout();
}

function updateGraphLayout() {
  const graph = document.getElementById("graph");
  let topOffset = 42;
  if (currentMode === "custom") {
    const panel = document.getElementById("custom-panel");
    topOffset += panel.offsetHeight;
  }
  graph.style.top = topOffset + "px";
  const svg = d3.select("#graph");
  svg.attr("height", window.innerHeight - topOffset);
  if (simulation) simulation.alpha(0.3).restart();
}

// ─── Article count display ─────────────────────────────────

document.getElementById("article-list").addEventListener("input", function() {
  const lines = this.value.split("\n").filter(l => l.trim());
  document.getElementById("article-count").textContent =
    lines.length ? lines.length + " article" + (lines.length === 1 ? "" : "s") : "";
});

// ─── Date dropdown ─────────────────────────────────────────

(function() {
  const sel = document.getElementById("date-preset");
  const d = new Date();
  for (let i = 0; i < 14; i++) {
    const dt = new Date(d);
    dt.setDate(dt.getDate() - i);
    const y = dt.getFullYear(), m = dt.getMonth() + 1, dd = dt.getDate();
    const label = y + "-" + String(m).padStart(2,'0') + "-" + String(dd).padStart(2,'0');
    const opt = document.createElement("option");
    opt.value = y + "/" + m + "/" + dd;
    opt.textContent = label;
    if (i === 0) opt.selected = true;
    sel.appendChild(opt);
  }
})();

// ─── Build handlers ─────────────────────────────────────────

document.getElementById("build-btn").addEventListener("click", () => {
  const val = document.getElementById("date-preset").value;
  const parts = val.split("/");
  loadGraph(parts[0], parts[1], parts[2]);
});

document.getElementById("build-custom-btn").addEventListener("click", () => {
  const textarea = document.getElementById("article-list");
  const lines = textarea.value.split("\n").map(l => l.trim()).filter(l => l);
  if (lines.length === 0) {
    textarea.focus();
    textarea.style.borderColor = "#e74c3c";
    setTimeout(() => textarea.style.borderColor = "", 2000);
    return;
  }
  loadGraphFromList(lines);
});

// ─── NDJSON streaming ──────────────────────────────────────

async function processNDJSON(resp) {
  const msgEl = document.getElementById("progress-msg");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  if (!resp.ok) {
    try {
      const text = await resp.text();
      showError("Server error (" + resp.status + "): " + text);
    } catch {
      showError("Server error (" + resp.status + ")");
    }
    return;
  }

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
          hideProgress();
          renderGraph(msg.data);
        } else if (msg.type === "error") {
          showError(msg.message);
        }
      } catch(e) {}
    }
  }
}

function loadGraph(year, month, day) {
  showProgress("Connecting to server...");
  fetch("/api/graph?year=" + year + "&month=" + month + "&day=" + day)
    .then(async resp => { await processNDJSON(resp); })
    .catch(err => { showError("Connection failed: " + err.message); });
}

function loadGraphFromList(titles) {
  showProgress("Starting...");
  fetch("/api/graph-from-list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titles: titles })
  })
    .then(async resp => { await processNDJSON(resp); })
    .catch(err => { showError("Connection failed: " + err.message); });
}

// ─── Progress helpers ──────────────────────────────────────

function showProgress(msg) {
  document.getElementById("progress-msg").textContent = msg;
  document.getElementById("progress").style.display = "block";
}
function hideProgress() {
  document.getElementById("progress").style.display = "none";
}
function showError(msg) {
  document.getElementById("progress-msg").textContent = "Error: " + msg;
  document.getElementById("progress").style.display = "block";
}

// ─── Graph rendering ───────────────────────────────────────

function renderGraph(data) {
  window._graphData = data;
  nodes = data.nodes.map(d => ({ ...d }));
  links = data.links.map(d => ({ ...d }));
  meta = data.meta;
  nodeMap = {};
  nodes.forEach(n => nodeMap[n.id] = n);

  document.getElementById("stats").textContent =
    meta.total_articles + " articles \u00b7 " + meta.total_nodes + " nodes \u00b7 " + meta.total_edges + " connections";

  const svg = d3.select("#graph");
  svg.selectAll("*").remove();
  svg.append("defs").append("clipPath").attr("id", "round-clip").append("circle").attr("r", 25);
  const container = svg.append("g").attr("class", "container");

  function getGraphTop() {
    return parseInt(document.getElementById("graph").style.top) || 42;
  }

  function resizeSVG() {
    svg.attr("width", window.innerWidth).attr("height", window.innerHeight - getGraphTop());
  }
  resizeSVG();
  window.addEventListener("resize", resizeSVG);

  function getCenter() {
    const el = document.getElementById("graph");
    const topVal = getGraphTop();
    const w = el.clientWidth || window.innerWidth || 1280;
    const h = el.clientHeight || window.innerHeight - topVal || 720;
    return [Math.max(w / 2, 400), Math.max(h / 2, 300)];
  }

  const zoom = d3.zoom().scaleExtent([0.1, 8]).on("zoom", event => {
    container.attr("transform", event.transform);
  });
  svg.call(zoom);

  function getCharge() {
    const topVal = getGraphTop();
    const w = window.innerWidth || 1280;
    const h = window.innerHeight - topVal || 720;
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

  nodes.forEach(d => {
    const [cx, cy] = getCenter();
    d.x = cx + (Math.random() - 0.5) * (getCenter()[0] * 1.2);
    d.y = cy + (Math.random() - 0.5) * (getCenter()[1] * 1.2);
  });

  const link = container.append("g").selectAll("line")
    .data(links).join("line")
    .attr("class", d => "link " + d.type)
    .attr("stroke-width", d => Math.max(0.5, Math.min(d.weight || 1, 3)));

  const node = container.append("g").selectAll("g")
    .data(nodes).join("g")
    .attr("class", d => "node" + (d.type === "helper" ? " helper" : ""))
    .call(d3.drag()
      .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    )
    .on("click", (event, d) => clickNode(d, data))
    .on("mouseover", (event, d) => {
      const name = d.title || d.label || d.id;
      const views = d.views ? " \u00b7 " + fmtViews(d.views) + " views" : "";
      const cluster = d.cluster ? " \u00b7 " + d.cluster : "";
      showTooltip(event, name + views + cluster);
      node.style("opacity", n => {
        if (n.id === d.id) return 1;
        const connected = links.some(l => {
          const sid = l.source.id || l.source;
          const tid = l.target.id || l.target;
          return (sid === d.id && tid === n.id) || (tid === d.id && sid === n.id);
        });
        return connected || n.type === "helper" ? 0.7 : 0.15;
      });
      link.style("opacity", l => {
        const sid = l.source.id || l.source;
        const tid = l.target.id || l.target;
        return sid === d.id || tid === d.id ? 0.6 : 0.05;
      });
    })
    .on("mouseout", () => {
      hideTooltip();
      node.style("opacity", null);
      link.style("opacity", null);
    });

  // Helper node toggle
  let showHelpers = true;
  document.getElementById("toggle-helpers").onchange = function() {
    showHelpers = this.checked;
    node.style("display", d => (d.type === "helper" && !showHelpers) ? "none" : null);
    link.style("display", l => {
      if (showHelpers) return null;
      return (l.type === "category" || l.type === "entity") ? "none" : null;
    });
  };

  // Spacing slider
  document.getElementById("spacing").oninput = function() {
    simulation.force("charge", d3.forceManyBody().strength(d => d.type === "helper" ? getCharge() * 0.2 : getCharge()));
    simulation.alpha(0.3).restart();
  };

  // Search
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

  // Tooltip
  function showTooltip(event, text) {
    d3.select("#tooltip")
      .style("display", "block")
      .style("left", (event.pageX + 12) + "px")
      .style("top", (event.pageY - 10) + "px")
      .html(text);
  }
  function hideTooltip() { d3.select("#tooltip").style("display", "none"); }

  node.each(function(d) {
    const el = d3.select(this);
    if (d.type === "helper") {
      el.append("circle").attr("r", d.size * 3 || 8).attr("fill", d.color || "#666");
      el.append("text").attr("dy", 4).attr("text-anchor", "middle").text(d.label || "");
    } else {
      const r = Math.min(Math.max(d.size * 1.5 || 12, 10), 30);
      el.append("circle").attr("r", r)
        .attr("fill", d.color || "#3498db")
        .attr("stroke", "rgba(255,255,255,0.3)").attr("stroke-width", 1.5);
      if (d.image_url) {
        el.append("image").attr("xlink:href", d.image_url)
          .attr("x", -r * 0.75).attr("y", -r * 0.75)
          .attr("width", r * 1.5).attr("height", r * 1.5)
          .attr("clip-path", "url(#round-clip)");
      }
      el.append("text").attr("dy", r + 12).attr("text-anchor", "middle")
        .text((d.title || "").length > 25 ? (d.title || "").slice(0, 22) + "..." : (d.title || ""));
    }
  });

  document.getElementById("side-panel").classList.remove("open");

  function ticked() {
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    node.attr("transform", d => "translate(" + d.x + "," + d.y + ")");
  }

  // Zoom to fit initially
  setTimeout(() => {
    const bounds = container.node().getBBox();
    const topVal = getGraphTop();
    const [w, h] = [window.innerWidth, window.innerHeight - topVal];
    if (bounds.width > 0 && bounds.height > 0) {
      const scale = Math.min(w / (bounds.width + 100), h / (bounds.height + 100), 2);
      const tx = w / 2 - (bounds.x + bounds.width / 2) * scale;
      const ty = h / 2 - (bounds.y + bounds.height / 2) * scale;
      svg.transition().duration(800).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }
  }, 500);
}

function clickNode(d, data) {
  if (d.type === "helper") return;
  const panel = document.getElementById("side-panel");
  const content = document.getElementById("panel-content");
  const connected = [];
  data.links.forEach(l => {
    const sid = l.source.id || l.source;
    const tid = l.target.id || l.target;
    if (sid === d.id) connected.push({ id: tid, type: l.type });
    else if (tid === d.id) connected.push({ id: sid, type: l.type });
  });

  const edgeIcon = { wikilink: "\ud83d\udd17", category: "\ud83d\udfe2", entity: "\ud83d\udfe0" };
  const clusterColors = {
    "Film & TV": "#e74c3c", "Music": "#9b59b6", "Sports": "#2ecc71",
    "Politics": "#3498db", "Technology": "#e67e22", "Science": "#1abc9c",
    "Culture": "#f39c12", "Business": "#34495e", "Health": "#e91e63",
    "World": "#00b894", "History": "#795548"
  };

  let html = '<span class="close" onclick="closePanel()">\u2715</span>';
  html += "<h2>" + escHtml(d.title || d.id) + "</h2>";
  html += '<div class="meta">';
  if (d.views) html += fmtViews(d.views) + " views";
  if (d.rank) html += (d.views ? " \u00b7 " : "") + "rank #" + d.rank;
  if (d.cluster) {
    html += ' <span class="cluster-tag" style="background:' + (clusterColors[d.cluster] || "#888") + '">' + escHtml(d.cluster) + "</span>";
  }
  html += "</div>";
  if (d.image_url && !d.image_url.includes("W.svg")) {
    html += '<img src="' + escHtml(d.image_url) + '" alt="' + escHtml(d.title) + '" onerror="this.style.display=\'none\'">';
  }
  const blurb = d.summary || d.extract;
  if (blurb) html += '<div class="summary">' + escHtml(blurb) + "</div>";
  if (connected.length > 0) {
    html += '<div class="connections"><h3>Connected (' + connected.length + ')</h3><ul>';
    connected.forEach(c => {
      const cn = data.nodes.find(n => n.id === c.id);
      html += '<li onclick="clickNode(nodeMap[\'' + c.id + '\'], window._graphData)">' + (edgeIcon[c.type] || "\u2022") + " " + escHtml(cn ? cn.title || cn.label : c.id) + "</li>";
    });
    html += "</ul></div>";
  }
  html += '<a class="ext-link" href="' + (d.url || "https://en.wikipedia.org/wiki/" + d.id) + '" target="_blank">Open on Wikipedia \u2192</a>';

  content.innerHTML = html;
  panel.classList.add("open");
}

function closePanel() { document.getElementById("side-panel").classList.remove("open"); }
function escHtml(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function fmtViews(v) {
  if (!v) return "";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toString();
}

// ─── Auto-load on page load ─────────────────────────────────

(function() {
  var sel = document.getElementById("date-preset");
  if (sel.options.length > 0) {
    var val = sel.options[0].value.split("/");
    window._graphData = null;
    window.clickNode = function(d) { clickNode(d, window._graphData || { nodes: nodes, links: links }); };
    loadGraph(val[0], val[1], val[2]);
  }

  // Listen for custom panel resize
  var resizeObserver = new ResizeObserver(function() { updateGraphLayout(); });
  resizeObserver.observe(document.getElementById("custom-panel"));
})();
</script>
</body>
</html>"""


class GraphAPIHandler(SimpleHTTPRequestHandler):

    def _write_json(self, obj):
        self.wfile.write((json.dumps(obj) + "\n").encode())
        self.wfile.flush()

    def _stream_graph(self, build_fn, *args, **kwargs):
        """Common NDJSON streaming for any build function."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            self._write_json({"type": "progress", "message": "Starting..."})
            graph_data = build_fn(
                *args,
                progress_callback=lambda m: self._write_json({"type": "progress", "message": m}),
                **kwargs,
            )
            self._write_json({"type": "graph", "data": graph_data})
        except Exception as e:
            self._write_json({"type": "error", "message": str(e)})

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

            self._stream_graph(
                build_graph, year, month, day,
                min_entity_share=min_entity,
                ignore_articles=ignore_list,
                user_agent=user_agent,
            )
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

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/graph-from-list":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
                titles = data.get("titles", [])
                if not titles or not isinstance(titles, list):
                    self.send_error(400, "Expected JSON with 'titles' array")
                    return
            except (ValueError, KeyError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON body")
                return

            self._stream_graph(build_graph_from_list, titles)
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
    print(f"  Viewer:       http://localhost:{port}")
    print(f"  Top Articles: http://localhost:{port}/api/graph?year=2026&month=5&day=29")
    print(f"  Custom List:  POST {port}/api/graph-from-list")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
