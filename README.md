# wikigraph

Build interactive connection graphs from Wikipedia, Wikimedia Commons, and
Wikidata items. Fetches article metadata, extracts named entities, identifies
shared categories and wikilinks, and exports a D3.js-compatible force-directed
graph.

```python
from wikigraph import build_graph

data = build_graph("2026", "5", "29")
# → {"meta": {...}, "nodes": [...], "links": [...]}
```

## Quickstart

### 1. Install

```bash
git clone https://github.com/fuzheado/wikigraph.git
cd wikigraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 2. Verify

```bash
python -m pytest tests/
# 36 passed
```

### 3. Build your first graph

```bash
# Build the Hatnote daily top 100 for a specific date
python -m wikigraph 2026 5 29 -o my_graph.json

# Output:
#   Fetching top 100 for 2026/5/29...
#   Got 99 articles
#   Fetching article metadata (async, 5 concurrent)...
#   Got metadata for 99 articles
#     2042 meaningful categories, 29707 total links
#   Extracting named entities with spaCy...
#   Found 817 unique named entities
#   Building graph...
#     109 direct wikilink edges between top 100 articles
#     99 articles + 60 helpers (43 categories, 17 entities) = 159 nodes
#     334 edges (109 wikilinks, 172 cat, 53 ent)
#   Graph saved to my_graph.json
```

Or from Python:

```python
from wikigraph import build_graph

graph = build_graph("2026", "5", "29")

print(f"{graph['meta']['total_articles']} articles")
print(f"{graph['meta']['total_nodes']} nodes")
print(f"{graph['meta']['total_edges']} connections")

# Inspect nodes
for node in graph["nodes"]:
    print(f"  {node.get('title', node.get('label', node['id']))} "
          f"({node['type']}, cluster={node.get('cluster', 'N/A')})")
```

### 4. Build from any article list

```bash
# From stdin (one article per line — handles titles with commas)
echo "Artificial intelligence" > articles.txt
echo "Machine learning" >> articles.txt
cat articles.txt | python -m wikigraph --stdin -o ai_graph.json

# Quick comma-separated list
python -m wikigraph --articles "Quantum computing,Qubit,Shor's algorithm" -o quantum.json

# Try a sample dataset — 120 architecture topics from WikiProject Architecture
cat architecture-articles.txt | python -m wikigraph --stdin -o architecture.json
python view_graph.py architecture.json
```

> Tip: Or open it in the **[web app](#6-run-the-web-server)** for the full interactive experience.
```

Or from Python:

```python
from wikigraph import build_graph_from_list

data = build_graph_from_list([
    "Artificial intelligence", "Machine learning", "Deep learning",
    "Neural network", "ChatGPT", "OpenAI"
])
print(f"{data['meta']['total_nodes']} nodes, {data['meta']['total_edges']} edges")
```

### 5. View the graph

#### Built-in interactive viewer

```bash
# View a pre-built graph
python view_graph.py my_graph.json

# Build and view in one step
python view_graph.py --date 2026 5 29

# Auto-find graph_data.json in current directory
python view_graph.py
```

Opens your browser with a D3.js force-directed graph. Same core features
as the web server (section 6) but for pre-built JSON files, with no
server-side build step needed. Zero extra dependencies.

#### Use with other tools

The JSON output follows the standard D3 force-graph format and works with
NetworkX, Gephi, Observable, or any D3 force layout:

```python
import json, networkx as nx

with open("my_graph.json") as f:
    data = json.load(f)

G = nx.node_link_graph(data)
print(f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
```

### 6. Run the web server

On startup, a welcome overlay lets you choose between **Top 100 Articles**
(today's most-viewed) and **Custom List** (paste your own titles), plus a
**language selector** for the Wikipedia edition (28 languages supported).
No graph auto-loads — you pick your mode and language first.

The web server serves the full web app from `index.html` with a polished
D3.js interface and two modes for building graphs:

```bash
# Start the server (default port 8000)
python server.py

# Or specify a port
python server.py 8080
```

Open **http://localhost:8000** in your browser. The web app is served
from `index.html` — a full D3.js interface that improves on the
static `view_graph.py` viewer with interactive builds, Play mode,
URL bookmarking, and more.

#### Top Articles mode

Select a date with the date picker (or navigate with ◀ ▶) to fetch that
day's Hatnote top 100 and generate a graph. Same data as the CLI
`python -m wikigraph 2026 5 29` command.

#### Custom List mode

Click the **Custom List** tab to switch modes. A right-side drawer panel
slides in where you can enter article titles. Three data sources are available:

**Manual entry** — Paste one Wikipedia article title per line.

**PagePile import** — Enter a PagePile ID and click Fetch. The titles are
loaded from the PagePile API and appended to your list.

**Category import** — Enter a Wikipedia category name (e.g. `Artificial
intelligence`) with a subcategory depth (0–2), capped at 500 articles.
Articles are fetched from the MediaWiki API and appended.

Click **Build Graph** to generate the graph from your list. Sources can
be combined — fetch from a category, add from a PagePile, then type a
few more by hand.

```text
Artificial intelligence
Machine learning
Deep learning
Neural network
ChatGPT
```

#### Controls

| Control | Action |
|---|---|
| **Search** | Filter articles by name in real-time |
| **Helpers** toggle | Show/hide category and entity helper nodes |
| **Labels** toggle | Show/hide all node labels |
| **Legend** toggle | Show/hide the color legend |
| **Spacing** slider | Adjust force simulation repulsion |
| **▶ Play / ⏹ Stop** | Auto-advance through articles; click to cycle speed (2s/3s/5s/8s) |
| **🔍 zoom, Aa size, 🔢 order** | Playback zoom, label font size, play order (rank/random) |
| **📷 Article / Wikidata** | Toggle image source for node thumbnails (no rebuild needed) |
| **⟳ Refresh** | Clear cache and rebuild (date mode) |
| **🔗 Share** | Copy a bookmarkable URL of the current graph |
| **☰ Panel** | Toggle the Custom List panel (in Custom List mode) |
| **Ignore** list | Exclude specific articles from the graph |
| **Hide** buttons | One-click filters (Social media, Geography) |
| **⚙ UA settings** | View/change User-Agent; non-compliant agents trigger a warning |
| **⚠ Failed articles** | Warning indicator with list of rate-limited articles |
| **Hover** | Highlight connected subgraph + tooltip |
| **Click** (article) | Open side panel with summary, image, and connections |
| **Click** (helper) | Open side panel with connected articles |
| **Drag** | Reposition nodes |
| **Scroll** | Zoom in/out |
| **Pan** | Click and drag background |

#### URL Parameters

All UI state can be set via URL parameters for bookmarking:

| Parameter | Values | Default | Description |
|---|---|---|---|
| `date` | `YYYY-MM-DD` | today | Load a specific date |
| `mode` | `custom` | — | Start in Custom List mode |
| `wiki` | language code | `en` | Wikipedia language edition (28 Hatnote-supported languages: ar, bn, ca, cs, da, de, el, en, es, et, fa, fi, fr, gl, hu, id, it, kn, ko, lv, no, or, pa, sv, ta, te, ur, zh) |
| `ignore` | comma-separated | defaults | Articles to exclude |
| `spacing` | `0`–`500` | `135` | Force repulsion |
| `helpers` | `0` or `1` | `1` | Show helpers |
| `labels` | `0` or `1` | `0` | Show labels |
| `legend` | `0` or `1` | `0` | Show legend |
| `speed` | `2`, `3`, `5`, `8` | `3` | Playback speed (seconds) |
| `zoom` | `0.5`–`3` | `1` | Playback zoom level |
| `fontsize` | `7`–`14` | `10` | Label font size |
| `order` | `rank` or `random` | `rank` | Playback order |
| `image` | `article` or `wikidata` | `article` | Image source for node thumbnails |

**Import parameters** (require `mode=custom`):

| Parameter | Values | Description |
|---|---|---|
| `pagepile` | PagePile ID | Fetch article titles from a PagePile list |
| `category` | category name | Fetch articles from a Wikipedia category |
| `depth` | `0`, `1`, `2` | Subcategory depth (requires `category`) |
| `list` | comma-separated | Article titles (URL-encoded, max ~50 for URL length) |
| `run` | `1` | Auto-build graph after importing (removed from URL after build) |

Examples:

```
?mode=custom&pagepile=40743&run=1
?mode=custom&category=Philosophy&depth=1
?mode=custom&list=ChatGPT,Deep%20learning,OpenAI
```

Use the **🔗 Share** button to copy a bookmarkable URL of the current state.

#### API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves `index.html` |
| `/api/graph?year=&month=&day=` | GET | NDJSON stream for date-based build |
| `/api/graph-from-list` | POST | NDJSON stream for custom article list (`{"titles": [...]}`) |
| `/api/pagepile?id=` | GET | Fetch article titles from a PagePile ID |
| `/api/category?name=&depth=` | GET | Fetch article titles from a Wikipedia category |

Both graph endpoints stream NDJSON with progress messages during the build,
followed by the graph data on success or an error on failure.

---

## Data Pipeline

```
                    ┌──────────────────────┐
                    │     Data Sources      │
                    │  • Hatnote top 100    │
                    │  • Custom list        │
                    │  • PagePile import    │
                    │  • Category members   │
                    └──────────┬───────────┘
                               │
          MediaWiki API ◄── fetch_all_metadata() (async, 3 concurrent)
                               │
                     ┌─────────┼─────────┐
                categories    links    extracts
                     │          │          │
            is_meaningful_     │     extract_entities()
              category()       │     (spaCy NER)
                     │          │          │
                     ▼          ▼          ▼
                ┌─────────────────────────────┐
                │      build_graph()          │
                │  NetworkX construction:     │
                │  • article nodes + clusters │
                        │  • wikilink edges           │
                        │  • category helpers         │
                        │  • entity helpers           │
                        └──────────────┬──────────────┘
                                       │
                              serialize_graph()
                                       │
                            {"nodes": [...], "links": [...]}
```

#### Image Sources

Article node images come from two sources, togglable in the web UI:

| Source | Field | Coverage |
|---|---|---|
| **Article** (MW) | `page_image_url` | Wikipedia article thumbnails from the MediaWiki API |
| **Wikidata** (P18) | `wikidata_image_url` | Wikimedia Commons images from the Wikidata P18 property (broader coverage) |

The Wikidata image source fills many gaps where MW API thumbnails aren't available.
Images are fetched via batch Wikidata API calls after the MW metadata step.

**Three connection types** are discovered:

| Type | Color | How it works |
|------|-------|-------------|
| **Wikilink** | Purple | Direct `[[links]]` between two articles in the set |
| **Category** | Green | Articles sharing a meaningful Wikipedia category (≥3 articles) |
| **Entity** | Orange | Articles referencing the same named entity — person, org, place, or event (≥3 articles) |

Category and entity connections appear as **helper nodes** — small intermediary
nodes that visually group related articles. This turns a sparse ~100-edge
wikilink-only graph into a rich ~400-edge network.

---

## API Reference

### Top-Level Functions

#### `build_graph(year, month, day, min_entity_share=3, verbose=True, ignore_articles=None, progress_callback=None, user_agent=None)`

Run the full pipeline: fetch → enrich → analyze → build → export.

```python
from wikigraph import build_graph

# Basic usage
data = build_graph("2026", "5", "17")

# Ignore specific articles, lower entity threshold, suppress output
data = build_graph(
    "2026", "5", "17",
    min_entity_share=2,
    verbose=False,
    ignore_articles=["Main Page", "Some_Article"],
)

# With progress streaming (useful for web servers)
messages = []
data = build_graph("2026", "5", "17", progress_callback=messages.append)
# messages → ["Fetching top 100...", "Fetched article metadata (5/100)", ...]

# Custom User-Agent (Wikimedia policy requires contact info)
data = build_graph("2026", "5", "17",
    user_agent="MyApp/1.0 (me@example.com)")
```

**Returns:** `dict` with keys:

| Key | Type | Description |
|-----|------|-------------|
| `meta` | `dict` | `{date, total_articles, total_nodes, total_edges, user_agent, ua_compliant, failed_articles, failed_count}` |
| `nodes` | `list[dict]` | Each node has `{id, type, title/label, size, color, cluster, image_url, ...}` |
| `links` | `list[dict]` | Each edge has `{source, target, weight, type}` |

#### `build_graph_from_list(titles, min_entity_share=3, verbose=True, progress_callback=None, user_agent=None)`

Build a connection graph from an arbitrary list of Wikipedia article titles.
Same pipeline as `build_graph()` but starts from a user-provided list instead
of the Hatnote top 100.

```python
from wikigraph import build_graph_from_list

data = build_graph_from_list([
    "Quantum computing", "Qubit", "Shor's algorithm",
    "Quantum supremacy", "Quantum entanglement"
])
# → same {meta, nodes, links} format as build_graph()
```

**Parameters:**
- `titles` — list of article titles (spaces or underscores OK)
- All other parameters same as `build_graph()`

#### `latest_available_date()`

Walk backwards from today to find the most recent date with Hatnote data.

```python
from wikigraph import latest_available_date

year, month, day = latest_available_date()
# → ("2026", "5", "29")
```

### Sources

#### `fetch_top100(year, month, day)`

Fetch the top 100 most-viewed English Wikipedia articles for a given date from
the Hatnote API. Results are cached for 24 hours.

```python
from wikigraph.sources.hatnote import fetch_top100

articles = fetch_top100("2026", "5", "17")
# → [{"id": "Article_Title", "title": "Article Title", "rank": 1,
#      "views": 500000, "summary": "...", "image_url": "...", ...}, ...]
```

#### `fetch_json(url, max_retries=2)`

Generic JSON fetcher with retry logic and Wikimedia-compliant User-Agent headers.

```python
from wikigraph.sources.hatnote import fetch_json

data = fetch_json("https://top.hatnote.com/en/wikipedia/2026/5/17.json")
```

### Enricher

#### `fetch_all_metadata(titles, max_concurrent=None, progress_callback=None, headers=None)`

Fetch categories, outgoing wikilinks, intro extracts, and page images for
multiple article titles from the MediaWiki API. Runs asynchronously with a
configurable concurrency limit (default 3). Results cached for 7 days.

```python
import asyncio
from wikigraph.enricher.mw_api import fetch_all_metadata

titles = ["Quantum_computing", "Qubit", "Shor's_algorithm"]
metadata = asyncio.run(fetch_all_metadata(titles))
# → {"Quantum_computing": {"categories": [...], "links": [...],
#      "extract": "...", "page_image_url": "..."}, ...}
```

**Parameters:**
- `titles` — list of article IDs (underscored, e.g. `"Albert_Einstein"`)
- `max_concurrent` — max simultaneous API calls (default from `WIKI_MAX_CONCURRENT` env var, 3)
- `progress_callback` — called with status string periodically
- `headers` — optional custom HTTP headers

### Analyzer

#### `is_meaningful_category(cat)`

Return `False` for Wikipedia maintenance categories ("Articles with short
description", "CS1 errors", etc.), `True` for topic categories ("2026 films",
"American novelists").

```python
from wikigraph.analyzer.categories import is_meaningful_category

is_meaningful_category("2026 films")                # → True
is_meaningful_category("Articles with short description")  # → False
```

#### `assign_cluster(categories, summary)`

Assign an article to a topic cluster by keyword matching against 11 predefined
groups: Sports, Music, Film & TV, Politics, Technology, Science & Nature,
History, Geography, Death & Crime, Business, Other.

```python
from wikigraph.analyzer.clustering import assign_cluster

cluster = assign_cluster(
    ["American mixed martial artists", "UFC fighters"],
    "Former UFC heavyweight champion from Nevada"
)
# → "Sports"
```

The 11 clusters are broad enough to cover the topics that typically trend in
Wikipedia's daily most-viewed list while being specific enough to create
meaningful visual groupings. They emerged from observing recurring patterns —
sporting events, entertainment releases, political news, celebrity deaths —
rather than from a formal taxonomy like Wikipedia's WikiProject hierarchy.
The keyword lists in `wikigraph/analyzer/clustering.py` can be customized for
different domains or languages.

#### `extract_entities(texts)`

Run spaCy NER on a dict of `{article_id: text}` to extract named entities
(people, organizations, places, events). Deduplicates variants and filters
noise (nationalities, common names).

```python
from wikigraph.analyzer.ner import extract_entities

texts = {
    "Page_A": "Netflix announced a new series produced by Shonda Rhimes.",
    "Page_B": "Shonda Rhimes signed an exclusive deal with Netflix.",
}
entity_map, _ = extract_entities(texts)
# entity_map → {"Netflix": ["Page_A", "Page_B"], "Shonda Rhimes": ["Page_A", "Page_B"]}
```

### Graph

#### `serialize_graph(G)`

Convert a NetworkX graph to the D3.js JSON format.

```python
import networkx as nx
from wikigraph.graph.serializers import serialize_graph

G = nx.Graph()
G.add_node("Alice", type="article", title="Alice", views=100000)
G.add_node("Bob", type="article", title="Bob", views=50000)
G.add_edge("Alice", "Bob", weight=1, type="wikilink")

nodes, links = serialize_graph(G)
# nodes → [{"id": "Alice", "type": "article", "size": 18, ...}, ...]
# links → [{"source": "Alice", "target": "Bob", "weight": 1, "type": "wikilink"}]
```

#### Graph builders (low-level)

```python
from wikigraph.graph.builder import (
    build_graph_nodes,
    add_wikilink_edges,
    add_category_helpers,
    add_entity_helpers,
)

G = nx.Graph()
articles = [{"id": "A", "categories": [...], "links": [...], ...}, ...]
article_ids = {a["id"] for a in articles}

build_graph_nodes(articles, G)
n_edges = add_wikilink_edges(articles, article_ids, G)
add_category_helpers(articles, article_ids, G, min_cat_share=3)
add_entity_helpers(articles, entity_map, G, min_entity_share=3)
```

### Cache

#### `_cache_get(cache_type, key, ttl)` / `_cache_set(cache_type, key, data)`

File-based JSON cache with type namespacing and TTL-based expiry.

```python
from wikigraph.cache import _cache_get, _cache_set

_cache_set("my_namespace", "my_key.json", {"data": 42})
result = _cache_get("my_namespace", "my_key.json", ttl=3600)
# → {"data": 42}  (None if expired or missing)
```

---

## Configuration

All settings are optional. Set them via environment variables or a `.env` file:

```bash
# .env
WIKI_USER_AGENT=MyApp/1.0 (me@example.com)
WIKI_MAX_CONCURRENT=5
WIKI_HATNOTE_CACHE_TTL=43200
```

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKI_USER_AGENT` | `WikiTop100Viz/1.0 (...)` | User-Agent for MW API. **Must include an email or URL** per Wikimedia policy. Non-compliant agents are rate-limited. |
| `WIKI_HATNOTE_URL` | `https://top.hatnote.com/...` | Hatnote API endpoint template (uses `{year}`, `{month}`, `{day}` placeholders) |
| `WIKI_MW_API` | `https://en.wikipedia.org/w/api.php` | MediaWiki API endpoint. Change for other wikis or Commons (`commons.wikimedia.org/w/api.php`). |
| `WIKI_MAX_CONCURRENT` | `3` | Concurrent async HTTP requests to MW API. Lower = gentler on API, higher = faster. |
| `WIKI_CACHE_DIR` | `.cache` | Directory for cached API responses. |
| `WIKI_HATNOTE_CACHE_TTL` | `86400` | Hatnote cache TTL in seconds (default 24h). |
| `WIKI_MW_CACHE_TTL` | `604800` | MediaWiki API cache TTL in seconds (default 7 days). |

---

## Output Format

The JSON output from `build_graph()` and `serialize_graph()`:

```json
{
  "meta": {
    "date": "2026-5-29",
    "total_articles": 99,
    "total_nodes": 159,
    "total_edges": 334,
    "user_agent": "WikiTop100Viz/1.0 (...)",
    "ua_compliant": true,
    "failed_articles": [],
    "failed_count": 0
  },
  "nodes": [
    {
      "id": "Article_Title",
      "type": "article",
      "title": "Article Title",
      "rank": 1,
      "views": 500000,
      "size": 24.3,
      "color": "#3498db",
      "cluster": "Film & TV",
      "summary": "Brief description...",
      "image_url": "https://upload.wikimedia.org/...",
      "url": "https://en.wikipedia.org/wiki/..."
    },
    {
      "id": "cat:2026 films",
      "type": "helper",
      "helper_type": "category",
      "label": "2026 films",
      "size": 3,
      "color": "#b0b0b0"
    },
    {
      "id": "ent:Netflix",
      "type": "helper",
      "helper_type": "entity",
      "label": "Netflix",
      "size": 2,
      "color": "#b0b0b0"
    }
  ],
  "links": [
    {"source": "Article_A", "target": "Article_B", "weight": 1, "type": "wikilink"},
    {"source": "cat:2026 films", "target": "Article_A", "weight": 1, "type": "category"},
    {"source": "ent:Netflix", "target": "Article_A", "weight": 1, "type": "entity"}
  ]
}
```

**Node types:**
- `article` — a Wikipedia page; sized by log-scaled view count, colored by topic cluster
- `helper` (with `helper_type`) — an intermediary node (shared category or named entity); small gray circle

**Edge types:**
- `wikilink` — direct `[[link]]` between two articles in the set
- `category` — article connected to a shared-category helper node
- `entity` — article connected to a shared-entity helper node

---

## Package Structure

```
wikigraph/
├── config.py          Environment variables and .env configuration
├── cache.py           File-based JSON cache with TTL
├── sources/           Data source plugins
│   ├── hatnote.py     Hatnote daily top-100 API
│   ├── pagepile.py    PagePile API — fetch article lists by ID
│   └── category.py    MediaWiki category member fetcher (with depth)
├── enricher/          MediaWiki API async batch enrichment
│   ├── mw_api.py      Fetch categories, links, extracts, page images
│   └── wikidata_images.py  Batch fetch P18 images from Wikidata API
├── analyzer/          NLP and classification
│   ├── categories.py  Maintenance category regex filter (80+ patterns)
│   ├── clustering.py  Keyword-based topic clustering (11 topics)
│   └── ner.py         spaCy NER with entity deduplication + noise filtering
├── graph/             NetworkX graph construction
│   ├── builder.py     Node, edge, and helper node construction
│   └── serializers.py NetworkX → D3 JSON + Cytoscape conversion
└── pipeline.py        Orchestration: fetch → enrich → analyze → build → export

index.html              D3.js force-directed graph web application (~1,500 lines)
view_graph.py          Browser-based interactive graph viewer (static file)
server.py              HTTP server (~190 lines) with web UI, graph API, and import endpoints
```

---

## Development

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm

# Run tests
python -m pytest tests/ -v

# Build a graph (date mode)
python -m wikigraph 2026 5 29 -o graph.json

# Build from article list
cat articles.txt | python -m wikigraph --stdin -o graph.json

# View in browser (static file viewer)
python view_graph.py graph.json

# Start the interactive web server
python server.py
# → http://localhost:8000 (serves index.html)
```

---

## Related Projects

- **[Wiki-Top-100](https://github.com/fuzheado/Wiki-Top-100)** — the interactive
  D3.js visualization app this library was extracted from. Running live at
  [wikiptop100.toolforge.org](https://wikiptop100.toolforge.org).
- **[hatnote/top](https://github.com/hatnote/top)** — the Hatnote project that
  provides daily Wikipedia pageview rankings.

## License

MIT — see [LICENSE](LICENSE).
