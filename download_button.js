// download_button.js – provides a helper to export the current graph as Cytoscape JSON

/**
 * Export the currently displayed graph in Cytoscape‑compatible JSON format and
 * trigger a download of the generated file.
 *
 * The function assumes that the global variable `graphData` holds the original
 * D3 JSON (with `meta`, `nodes`, `links`). The D3 simulation creates a local
 * `nodes` array that contains the up‑to‑date `x`/`y` positions after layout.
 * The renderGraph() function stores that array on the window as `_d3_nodes`
 * (see the edit in index.html).
 */
function downloadCytoscape() {
  if (typeof graphData === "undefined" || !graphData) {
    alert("No graph data available – load a graph first.");
    return;
  }

  // The D3 simulation copies the original nodes into a fresh array; we expose
  // that array globally as `window._d3_nodes` (added in index.html).
  const d3Nodes = window._d3_nodes || (typeof simulation !== "undefined" && simulation.nodes ? simulation.nodes() : []);

  // Build Cytoscape structure
  const cyt = {
    meta: graphData.meta || {},
    elements: {
      nodes: [],
      edges: []
    }
  };

  // Convert nodes – preserve all original attributes, expose position if known.
  d3Nodes.forEach(function (d) {
    const nodeData = {
      id: d.id,
      label: d.title || d.label || d.id
    };
    // Copy any additional fields (size, color, cluster, etc.)
    for (const key in d) {
      if (key === "id" || key === "title" || key === "label") continue;
      // Avoid copying internal D3 properties like __proto__ etc.
      if (Object.prototype.hasOwnProperty.call(d, key)) {
        nodeData[key] = d[key];
      }
    }
    const nodeEntry = { data: nodeData };
    // Include layout position if we have numeric coordinates
    if (typeof d.x === "number" && typeof d.y === "number") {
      nodeEntry.position = { x: d.x, y: d.y };
    }
    cyt.elements.nodes.push(nodeEntry);
  });

  // Convert edges – keep source/target, type and weight.
  (graphData.links || []).forEach(function (e) {
    const edgeData = {
      id: `${e.source}→${e.target}`,
      source: e.source,
      target: e.target,
      type: e.type,
      weight: e.weight
    };
    cyt.elements.edges.push({ data: edgeData });
  });

  const jsonStr = JSON.stringify(cyt, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  // Create a filename like "wikigraph_cytoscape_2026-05-29.json"
  const datePart = (graphData.meta && graphData.meta.date) ? graphData.meta.date.replace(/[^0-9]/g, "_") : "graph";
  a.download = `wikigraph_cytoscape_${datePart}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
