# wikigraph — Roadmap

## Near-term (next session or two)

### Focus subgraph
Click a node to show only that article and its direct connections. The 300-node
hairball becomes an 8-node readable cluster. Click again to unfocus. This is
the single highest-impact UX improvement for navigating dense graphs.

### Pin / unpin indicator
Dragging a node already sets `fx`/`fy` to lock it in place, but there's no
visual indicator. A pin button in the side panel (with a visual marker on the
node) would make this explicit.

### Copy article title
Small button in the side panel next to the article title. Common workflow:
see an interesting connection, want to add it to a custom list or look it up.

### Build subgraph from selection
Select 2–3 nodes, click "Focus on selection" → rebuild graph from just those
articles and their interconnections. Like drilling down into a cluster.

### Add to ignore from side panel
Per-article "Hide" button in the side panel. Less destructive than the global
ignore list — useful for quickly decluttering.

---

## Medium-term

### Multi-language support
See [MULTI_LANGUAGE.md](MULTI_LANGUAGE.md) for the full analysis. Summary:

| Component | Difficulty | Effort |
|---|---|---|
| MediaWiki API (swap hostname) | Trivial | One config change |
| Hatnote Top 100 (swap language code) | Trivial | One URL param |
| PagePile / Wikidata / Page images | Trivial | Already multi-language |
| Category filtering (maintenance patterns) | Moderate | Statistical fallback + per-language overrides |
| spaCy NER (25 languages have models) | Hard | Language→model map + `xx_ent_wiki_sm` fallback |
| Topic clustering (English keywords) | Hard | Wikidata-based clustering (language-agnostic) |
| UI i18n | Hard (optional) | Core function works with English UI on any wiki |

Recommended first step: add a `?wiki=` URL parameter and wiki selector. Swap
MW API hostname + Hatnote language code. Works immediately for ~30 languages,
degrading gracefully where NER/clustering don't have full coverage.

### Graph export
Download graph as PNG, SVG, or JSON. The `view_graph.py` viewer already has a
static-file mode. Extending to the web app with a download button is
straightforward.

### Expand connections
For a selected node, fetch all articles that link to it (not just the
ones already in the graph) and add them. Turns the graph into an interactive
exploration tool rather than a static snapshot.

---

## Longer-term

### Wikidata SPARQL queries as data sources
Pre-built SPARQL queries — "all films starring X", "paintings in the Louvre",
"earthquakes above magnitude 7" — as graph inputs. Already supported by the
pipeline architecture (any source that produces a title list works).

### Geospatial visualization
Integrate Kepler.gl for geographic graphs. Many articles have coordinates
via Wikidata. Map layers alongside the force graph — or switch between them.

### Article filtering
Filter by cluster ("show only Sports"), view count range, or date range.
Currently the Search box filters by name in real-time; extending to structural
properties is a natural next step.

### Node grouping
Collapse category and entity helper nodes into their parent articles.
Reduces visual clutter while preserving the connection data.

### LLM summaries
Generate article summaries via an LLM for the side panel when the MediaWiki
extract isn't sufficient. The pipeline already includes extracts — this would
be an enhancement, not a replacement.

### Multi-wiki support (Commons, Wikisource, Wikivoyage)
Extend beyond Wikipedia to other Wikimedia projects. Commons files, Wikisource
texts, and Wikivoyage destinations all have interconnections worth visualizing.

### Cytoscape export improvements
The Cytoscape endpoint already exists (`/api/graph-from-cytoscape`) but needs
Python 3.13+ compatibility (currently `cgi`-dependent) and a dedicated upload UI.

---

## Completed ✅

- **PagePile import** — Enter ID, Fetch, titles appended to custom list
- **Category import** — Category name + depth selector (0–2), capped at 500 articles, MW API fetch
- **Startup overlay** — Choose mode on load; no more auto-loading bug
- **Custom List right-side drawer** — 400px slide-in panel replacing flat dropdown
- **URL import parameters** — `pagepile=`, `category=`, `depth=`, `list=`, `run=1`
- **Share button** — Copies bookmarkable URL of current graph state
- **Date picker fix** — Only processes on Enter/blur, not partial typing
- **Error overlay** — Friendly messages instead of raw 404 URLs
- **Mode switch guard** — Warns before discarding unsaved custom list
- **Custom list summaries** — Populate from MediaWiki extracts
- **Python 3.14 compatibility** — `cgi` import moved; cytoscape returns 501 on 3.13+
