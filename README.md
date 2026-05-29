# wikigraph

Build interactive connection graphs from Wikipedia, Wikimedia Commons, and
Wikidata items.

```
pip install wikigraph
```

## Quickstart

```python
from wikigraph import build_graph

# Build a graph from the Hatnote daily top 100
data = build_graph("2026", "5", "29")
print(f"{data['meta']['total_nodes']} nodes, {data['meta']['total_edges']} edges")
```

```bash
# CLI
python -m wikigraph.pipeline 2026 5 29 -o graph.json
```

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
│   ├── categories.py  Maintenance category filtering
│   ├── clustering.py  Keyword-based topic clustering
│   └── ner.py         spaCy named entity recognition
├── graph/             NetworkX graph construction
│   ├── builder.py     Node, edge, and helper node construction
│   └── serializers.py NetworkX → D3 JSON serialization
└── pipeline.py        Orchestration: fetch → enrich → analyze → build → export
```

## Requirements

- Python 3.12+
- httpx, networkx, spacy (+ en_core_web_sm model), click

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).
