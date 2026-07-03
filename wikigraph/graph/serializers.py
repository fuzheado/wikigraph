"""Graph serialization — NetworkX to D3.js JSON format.

Converts a NetworkX graph into the {nodes: [...], links: [...]} format
expected by the D3.js force-directed graph visualization.
"""
import math

from .builder import HELPER_COLOR
from ..analyzer.clustering import CLUSTER_COLORS


def serialize_graph(G):
    """Serialize a NetworkX graph to the existing D3 JSON format.
    Returns a tuple (nodes_data, links_data) where each entry is a list of
    dicts ready for JSON dumping.
    """
    """Convert NetworkX graph to JSON-serializable format.

    Strips intermediate keys (core_cats, links, extract, history) from
    article nodes. Helper nodes get HELPER_COLOR. Article sizes are
    log-scaled from view counts (range 6-35).
    """
    nodes_data = []
    for nid, ndata in G.nodes(data=True):
        node = dict(ndata)
        node["id"] = nid
        if node.get("type") == "article":
            node["color"] = CLUSTER_COLORS.get(node.get("cluster", "Other"), CLUSTER_COLORS["Other"])
            views = node.get("views", 0) or 1000  # handle 0 and missing
            node["size"] = max(6, min(35, math.log2(views) * 2.5))
        else:
            node["color"] = HELPER_COLOR
        for k in ("core_cats", "links", "history"):
            node.pop(k, None)
        nodes_data.append(node)

    links_data = []
    for s, t, edata in G.edges(data=True):
        links_data.append({
            "source": s,
            "target": t,
            "weight": edata.get("weight", 1),
            "type": edata.get("type", "unknown"),
        })

    return nodes_data, links_data

def convert_to_cytoscape(data):
    """Convert the D3‑style graph dict (as returned by ``build_graph``) to a
    Cytoscape‑compatible JSON structure.

    The output shape is:
    {
        "meta": {...},
        "elements": {
            "nodes": [{"data": {...}, "position": {...?}}, ...],
            "edges": [{"data": {...}}, ...]
        }
    }
    Any extra fields present on the original nodes/links are preserved inside
    the ``data`` object. ``position`` is added only if the source dict contains
    ``_x`` and ``_y`` keys (which we can set from the UI after a drag).
    """
    # Guard against malformed input
    if not isinstance(data, dict) or "nodes" not in data or "links" not in data:
        raise ValueError("Invalid graph data – expected keys 'nodes' and 'links'")

    cyt_nodes = []
    for n in data["nodes"]:
        node_data = {
            "id": n.get("id"),
            "label": n.get("title") or n.get("label") or n.get("id"),
        }
        # Copy over all other attributes
        for k, v in n.items():
            if k in ("id", "title", "label"):
                continue
            # Avoid copying internal D3 properties like __proto__ etc.
            if Object.prototype.hasOwnProperty.call(n, k):
                node_data[k] = v
        node_entry: dict = {"data": node_data}
        # Include layout position if we have numeric coordinates
        if "_x" in n and "_y" in n:
            node_entry["position"] = {"x": n["_x"], "y": n["_y"]}
        cyt_nodes.append(node_entry)

    cyt_edges = []
    for e in data["links"]:
        edge_id = f"{e.get('source')}→{e.get('target')}"
        edge_data = {
            "id": edge_id,
            "source": e.get("source"),
            "target": e.get("target"),
            "type": e.get("type"),
            "weight": e.get("weight"),
        }
        cyt_edges.append({"data": edge_data})

    return {
        "meta": data.get("meta", {}),
        "elements": {
            "nodes": cyt_nodes,
            "edges": cyt_edges,
        },
    }

def convert_from_cytoscape(cyt_data):
    """Convert Cytoscape‑compatible JSON back to the internal D3 format.
    Expected structure:
        {
            "meta": {...},
            "elements": {
                "nodes": [{"data": {...}, "position": {"x":…, "y":…}}, …],
                "edges": [{"data": {...}}, …]
            }
        }
    Returns a dict with ``meta``, ``nodes`` and ``links`` keys matching the
    format produced by ``serialize_graph``.
    """
    if not isinstance(cyt_data, dict) or "elements" not in cyt_data:
        raise ValueError("Invalid Cytoscape JSON – missing 'elements'")
    nodes = []
    for n in cyt_data["elements"].get("nodes", []):
        d = n.get("data", {})
        # Preserve layout positions if present
        if "position" in n:
            pos = n["position"]
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                d["_x"] = pos["x"]
                d["_y"] = pos["y"]
        nodes.append(d)

    links = []
    for e in cyt_data["elements"].get("edges", []):
        d = e.get("data", {})
        links.append({
            "source": d.get("source"),
            "target": d.get("target"),
            "weight": d.get("weight", 1),
            "type": d.get("type", "unknown"),
        })

    return {
        "meta": cyt_data.get("meta", {}),
        "nodes": nodes,
        "links": links,
    }

    """Convert the D3‑style graph dict (as returned by ``build_graph``) to a
    Cytoscape‑compatible JSON structure.

    The output shape is:
    {
        "meta": {...},
        "elements": {
            "nodes": [{"data": {...}, "position": {...?}}, ...],
            "edges": [{"data": {...}}, ...]
        }
    }
    Any extra fields present on the original nodes/links are preserved inside
    the ``data`` object. ``position`` is added only if the source dict contains
    ``_x`` and ``_y`` keys (which we can set from the UI after a drag).
    """
    # Guard against malformed input
    if not isinstance(data, dict) or "nodes" not in data or "links" not in data:
        raise ValueError("Invalid graph data – expected keys 'nodes' and 'links'")

    cyt_nodes = []
    for n in data["nodes"]:
        node_data = {
            "id": n.get("id"),
            "label": n.get("title") or n.get("label") or n.get("id"),
        }
        # Copy over all other attributes
        for k, v in n.items():
            if k in ("id", "title", "label"):
                continue
            node_data[k] = v
        node_entry: dict = {"data": node_data}
        # Optional position for layout persistence
        if "_x" in n and "_y" in n:
            node_entry["position"] = {"x": n["_x"], "y": n["_y"]}
        cyt_nodes.append(node_entry)

    cyt_edges = []
    for e in data["links"]:
        edge_id = f"{e.get('source')}→{e.get('target')}"
        edge_data = {
            "id": edge_id,
            "source": e.get("source"),
            "target": e.get("target"),
            "type": e.get("type"),
            "weight": e.get("weight"),
        }
        cyt_edges.append({"data": edge_data})

    return {
        "meta": data.get("meta", {}),
        "elements": {
            "nodes": cyt_nodes,
            "edges": cyt_edges,
        },
    }

