# wikigrapher — Handoff Document

## What It Is

Build interactive connection graphs from Wikipedia, Wikimedia Commons, and
Wikidata. Fetches article metadata, extracts named entities, identifies shared
categories and wikilinks, and exports a D3.js force-directed graph with three
connection types (wikilinks, shared categories, shared entities).

Four input sources:
- **Top Articles** — daily top 100 from the Hatnote API
- **Custom List** — any list of Wikipedia article titles (one per line)
- **PagePile** — fetch article lists by PagePile ID
- **Category** — fetch members of a Wikipedia category (with subcategory depth 0–2)

## Quickstart

```bash
source .venv/bin/activate

# CLI: build a graph
python -m wikigraph 2026 5 29 -o graph.json

# Web app
python server.py
# → http://localhost:8000

# Tests
python -m pytest tests/ -v
```

## Project Structure

```
wikigraph/
├── config.py              Environment variables and .env configuration
├── cache.py               File-based JSON cache with TTL
├── sources/
│   ├── hatnote.py         Hatnote daily top-100 API
│   ├── pagepile.py        PagePile API — fetch article lists by ID
│   └── category.py        Category member fetcher (with subcategory depth)
├── enricher/
│   ├── mw_api.py          MediaWiki API: categories, links, extracts, page images, QIDs
│   └── wikidata_images.py Wikidata P18 image batch fetcher
├── analyzer/
│   ├── categories.py      Maintenance category regex filter (80+ patterns)
│   ├── clustering.py      Keyword-based topic clustering (11 topics)
│   └── ner.py             spaCy NER with entity deduplication + noise filtering
├── graph/
│   ├── builder.py         NetworkX graph construction (nodes, edges, helpers)
│   └── serializers.py     NetworkX → D3 JSON + Cytoscape serialization
└── pipeline.py            Orchestration: fetch → enrich → analyze → build → export

index.html                 D3.js web application (~1,500 lines, served by server.py)
view_graph.py              Static file viewer for pre-built JSON
server.py                  HTTP server (~190 lines): web UI + 4 API endpoints
Dockerfile                 Toolforge container build
Procfile                   Build service process definition
DEPLOY_TOOLFORGE.md        Toolforge deployment guide
```

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
          MediaWiki API (async, 3 concurrent) ◄── fetch_all_metadata()
          (categories, links, extracts, page images, wikibase_item QID)
                               │
                     ┌─────────┼────────┐
                categories   links   extracts
                     │         │        │
            is_meaningful_      │  extract_entities()
              category()        │  (spaCy NER)
                     │          │        │
                Wikidata P18 image fetch (batch, 50/request)
                               │
                     ┌─────────┼────────┐
                     ▼         ▼        ▼
                ┌──────────────────────────┐
                │      build_graph()        │
                │  NetworkX construction:   │
                │  • article nodes          │
                │  • wikilink edges         │
                │  • category helpers       │
                │  • entity helpers         │
                └───────────┬──────────────┘
                            │
                   serialize_graph()
                            │
                 {"nodes": [...], "links": [...]}
```

### Three connection types

| Type | Color | Prefixed ID | How it works |
|------|-------|-------------|
| **Wikilink** | Purple | — | Direct `[[links]]` between two articles |
| **Category** | Green | `cat:` | Shared meaningful categories (≥3 articles) |
| **Entity** | Orange | `ent:` | Shared named entities — person, org, place, event (≥3 articles) |

### Image sources

| Source | Field | API | Coverage |
|--------|-------|-----|----------|
| Article (MW) | `page_image_url` | MediaWiki `pageimages` | Articles with infobox images |
| Wikidata (P18) | `wikidata_image_url` | Wikidata `wbgetentities` + Commons | Broader — fills MW gaps |

## Key Files

### `server.py`
HTTP server (~190 lines). Serves `index.html` as a static file.
Four API endpoints:
- `GET /api/graph?year=&month=&day=` — date-based build via `build_graph()`
- `POST /api/graph-from-list` — custom list via `build_graph_from_list()`
- `GET /api/pagepile?id=` — fetch article titles from a PagePile ID
- `GET /api/category?name=&depth=` — fetch titles from a Wikipedia category

All graph endpoints return NDJSON: progress messages (`{"type":"progress","message":"..."}`)
followed by the final graph (`{"type":"graph","data":{...}}`) or error.
Import endpoints return JSON with `{titles, total, ...}`.

### `index.html`
Standalone (~1,500 lines) D3.js web app. Key features:
- **Startup overlay** — choose Top 100 or Custom List on load; no auto-loading
  - **Language selector** — pick Wikipedia edition (12 languages) before generating
- Two-row control bar with mode tabs (Top Articles / Custom List)
- Date picker with ◀ ▶ navigation; only fires on Enter/blur (no partial-date loads)
- **Custom List right-side drawer** (400px slide-in panel)
  - Manual entry textarea (one article per line)
  - **PagePile import** — enter ID, click Fetch, titles appended
  - **Category import** — enter category name + depth (0–2), capped at 500 articles
  - 200+ article warning; source results append so you can combine sources
  - ☰ Panel toggle button in control bar
- **Mode switching guard** — warns before discarding unsaved custom list
- Search, Helpers/Labels/Legend toggles, Spacing slider
- Play mode (auto-advance, speed/zoom/font/order controls)
- Image source toggle (Article MW / Wikidata P18) — live switch, no rebuild
- Ignore list with tag chips; Hide buttons (Social, Geography)
- ⟳ Refresh (clear cache + rebuild)
- ⚙ UA settings panel; ⚠ Failed articles warning
- About modal with legend
- **Error overlay** — centered, auto-hiding error messages (no raw 404 URLs)
- **Wiki language selector** — 28 languages (all Hatnote-supported editions)
  — switches MW API, Hatnote, and spaCy model per language
- **URL import parameters** — `pagepile=`, `category=`, `depth=`, `list=`, `run=1`
  auto-populate the custom list and optionally build the graph
- **🔗 Share button** — copies a bookmarkable URL of the current graph state
- URL parameter sync for all state (bookmarkable)
- Side panel with image, summary, connected articles
- Hover highlighting, drag, zoom/pan
- ResizeObserver for dynamic layout

### `wikigraph/pipeline.py`
Two entry point functions:

#### `build_graph(year, month, day, ...)`
1. `fetch_top100()` — Hatnote API
2. `fetch_all_metadata()` — MW API (async, 3 concurrent)
3. `fetch_wikidata_images_batch()` — Wikidata P18 images
4. `extract_entities()` — spaCy NER
5. `build_graph_nodes()` + edge/helper functions → NetworkX
6. `serialize_graph()` → D3 JSON

#### `build_graph_from_list(titles, ...)`
Same as above but starts from a list of titles instead of Hatnote.
Uses `min_cat_share=2` (vs 3 for date mode) since small lists need looser grouping.

### `wikigraph/enricher/wikidata_images.py`
Batch fetches P18 (image) from Wikidata API. 50 QIDs per request.
Converts Commons filenames to `upload.wikimedia.org` thumbnail URLs
using MD5 hash path. Handles rate limits with exponential backoff.

### Caching
- Hatnote: 24h TTL (`.cache/hatnote/`)
- MW API: 7-day TTL (`.cache/mw/`)
- File-based JSON cache via `cache.py`
- Clear with `rm -rf .cache` or `?refresh=1` in API

## Recent Changes (Current Session)

```
—        feat: multi-language support — ?wiki= param, MW API/Hatnote/spaCy per language
—        feat: startup language selector — pick Wikipedia edition before generating
—        fix: pass wiki to fetch_top100; language-prefixed MW API cache keys
—        feat: statistical category filter — language-agnostic maintenance removal
—        fix: startup overlay — no more auto-load on page load; blank canvas until user chooses
—        feat: right-side drawer panel for Custom List (was flat bottom dropdown)
—        feat: PagePile import source (wikigraph/sources/pagepile.py + /api/pagepile)
—        feat: Category import source (wikigraph/sources/category.py + /api/category)
—        fix: date picker only processes on Enter/blur, not on partial typing
—        fix: graceful error messages (centered overlay, friendly date-format text, no raw 404 URLs)
—        fix: mode switch guard — warns before discarding unsaved custom list
—        fix: custom list summaries now populate from MediaWiki extracts
—        fix: Python 3.14 compatibility — moved cgi import inside cytoscape handler
—        fix: duplicate POST handler code removed from server.py

9ab4e47  feat: Wikidata P18 image enrichment + image source toggle
92f43bc  feat: standalone web app UI (index.html) with full control panel
124cc72  docs: web server section + polish README
7eb01ec  feat: Custom List mode with textarea UI and POST API
b0ea6b1  feat: Toolforge deployment infrastructure
```

## Running the Server

```bash
python server.py           # default port 8000 (works with Python 3.10–3.14)
python server.py 8080      # custom port
```

## Tests

```bash
python -m pytest tests/ -v     # 36 tests
```

The test suite uses mocked cache data and doesn't hit live APIs.
If you need to clear caches for fresh API responses:

```bash
rm -rf .cache
```

## URL Parameters (bookmarkable)

All UI state can be set via URL:
```
http://localhost:8000/?date=2026-05-29&play=1&speed=5&zoom=2&order=random&image=wikidata
```

Key params: `date`, `mode=custom`, `ignore`, `spacing`, `helpers`, `labels`,
`legend`, `speed`, `zoom`, `fontsize`, `order`, `image`.

**Import parameters** (require `mode=custom`):
- `pagepile=NNNN` — fetch articles from a PagePile ID
- `category=NAME` — fetch articles from a category (with optional `depth=0-2`)
- `list=TITLE1,TITLE2,...` — comma-separated article titles (URL-encoded, max ~50)
- `run=1` — auto-build the graph after importing (stripped from URL after build)

Examples:
```
?mode=custom&pagepile=40743&run=1
?mode=custom&category=Philosophy&depth=1
?mode=custom&list=ChatGPT,Deep%20learning,OpenAI&run=1
```

Use the **🔗 Share** button in the control bar to copy the current URL.

## Toolforge Deployment

See `DEPLOY_TOOLFORGE.md` for deploying to Toolforge as a build service.
`Dockerfile` and `Procfile` are configured. The server reads `$PORT` env var.

## Future Possibilities

See **[ROADMAP.md](ROADMAP.md)** for the full roadmap with priorities and status.
See **[MULTI_LANGUAGE.md](MULTI_LANGUAGE.md)** for the multi-language support analysis.

### Completed
- ~~PagePile import~~ — Done. Enter ID, Fetch, titles appended to list.
- ~~Category import~~ — Done. Category name + depth selector, MW API fetch.

### High priority
- **Focus subgraph** — Click a node to show only it and its direct connections.
  The biggest quality-of-life improvement for navigating dense graphs.
- **Pin/unpin nodes** — Visual indicator for pinned nodes in the side panel.
  Drag already sets fx/fy under the hood.

### Medium priority
- **Copy article title** — Small button in the side panel to copy the title.
- **Build subgraph from selection** — Select 3 nodes, rebuild graph from just
  those articles and their interconnections.

### Backlog
- **Add to ignore from side panel** — Per-article hide button (less destructive
  than the global ignore list).
- **Expand connections** — Fetch all articles that link to a selected node
  (not just the ones already in the graph) and add them.
- **Graph export** — Download graph as PNG/SVG/JSON
- **Wikidata SPARQL queries** — Pre-built SPARQL queries as data sources
- **Geospatial map** — Integrate Kepler.gl for geographic visualization
- **Article filtering** — Filter by cluster, view count range, date range
- **Node grouping** — Collapse categories/entities into their articles
- **Multi-wiki** — Support other Wikimedia projects (Commons, Wikisource)
- **LLM summaries** — Generate article summaries via LLM for the side panel

## Common Pitfalls

1. **Stale cache** — After changing MW API parameters (like adding `pageprops`),
   delete `.cache/mw/` to force fresh fetches.
2. **Port in use** — `lsof -i :<port>` to find and kill old server processes.
3. **Wikidata rate limits** — The batch fetcher handles this with backoff, but
   very large article lists (>500) may hit limits. Increase `BATCH_SIZE` or add
   delays in `wikidata_images.py`.
4. **spaCy model missing** — `python -m spacy download en_core_web_sm` required.
5. **User-Agent** — Must include contact info (email or URL) or MW API will
   429 rate-limit. Set via `WIKI_USER_AGENT` env var, `.env` file, or the
   ⚙ UA panel in the UI.
6. **Python 3.13+** — The `cgi` module was removed. The cytoscape upload endpoint
   returns 501 on Python 3.13+. All other endpoints work normally.
