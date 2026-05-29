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
python -m wikigraph.pipeline 2026 5 29 -o my_graph.json

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

### 4. View the graph

#### Built-in interactive viewer

```bash
# View a pre-built graph
python view_graph.py my_graph.json

# Build and view in one step
python view_graph.py --date 2026 5 29

# Auto-find graph_data.json in current directory
python view_graph.py
```

Opens your browser with a D3.js force-directed graph — search, hover
highlighting, drag nodes, zoom/pan, tooltips. Zero extra dependencies.

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

---

## Data Pipeline

```
Hatnote API ──► fetch_top100() ──► [article list]
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
│   └── hatnote.py     Hatnote daily top-100 API
├── enricher/          MediaWiki API async batch enrichment
│   └── mw_api.py      Fetch categories, links, extracts, page images
├── analyzer/          NLP and classification
│   ├── categories.py  Maintenance category regex filter (80+ patterns)
│   ├── clustering.py  Keyword-based topic clustering (11 topics)
│   └── ner.py         spaCy NER with entity deduplication + noise filtering
├── graph/             NetworkX graph construction
│   ├── builder.py     Node, edge, and helper node construction
│   └── serializers.py NetworkX → D3 JSON serialization
└── pipeline.py        Orchestration: fetch → enrich → analyze → build → export

view_graph.py          Browser-based interactive graph viewer
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

# Build a graph
python -m wikigraph.pipeline 2026 5 29 -o graph.json

# View in browser
python view_graph.py graph.json
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
