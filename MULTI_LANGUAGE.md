# Multi-language Support

Analysis of what it would take for wikigraph to support any language edition
of Wikipedia — not just English.

---

## Current state

Everything is hardcoded for English Wikipedia (`en.wikipedia.org`):

- Hatnote API: `top.hatnote.com/en/wikipedia/...`
- MW API: `en.wikipedia.org/w/api.php`
- spaCy NER model: `en_core_web_sm`
- Category filter patterns: 80+ English-specific regexes
- Topic clustering keywords: 100% English words
- UI: all labels, buttons, help text in English

---

## Component-by-component analysis

### 1. MediaWiki API — Trivial

Change the API host from `en.wikipedia.org` to `fr.wikipedia.org`,
`de.wikipedia.org`, etc. The Action API and REST API are identical across
all 300+ language editions.

```python
# Current
MW_API = "https://en.wikipedia.org/w/api.php"
# Future
MW_API = f"https://{lang}.wikipedia.org/w/api.php"
```

Everything downstream works unchanged: categories, extracts, links, page images
all return in the target language.

### 2. Hatnote Top 100 — Trivial

Hatnote already supports many languages. The URL pattern is:

```
https://top.hatnote.com/{lang}/wikipedia/{year}/{month}/{day}.json
```

Examples:
- `https://top.hatnote.com/de/wikipedia/2026/7/3.json` (German)
- `https://top.hatnote.com/fr/wikipedia/2026/7/3.json` (French)
- `https://top.hatnote.com/ja/wikipedia/2026/7/3.json` (Japanese)

~30 languages available. For languages not covered by Hatnote, the Wikimedia
Pageviews API (`wikimedia.org/api/rest_v1/metrics/pageviews/top`) provides
equivalent data for all wikis.

### 3. PagePile — Trivial

Each PagePile identifies its wiki (`enwiki`, `dewiki`, `frwiki`). The API
returns whatever the pile contains — no language awareness needed in our code.

### 4. Wikidata images — Trivial

Wikidata is inherently multilingual and language-agnostic. QIDs and P18
(property for images) work the same for every language.

### 5. Category filtering — Moderate

The 80+ maintenance category regex patterns in `categories.py` are entirely
English-specific:

```python
r'^articles?\s+(with|containing|needing)'
r'^living\s+people\b'
r'\bunsourced\s+statements\b'
r'\bdead\s+(external\s+)?links?\b'
```

Every Wikipedia language has its own maintenance category conventions. German
uses `"Wikipedia:"` prefix patterns; Japanese has different structural
categories entirely.

**Approaches:**

- **Per-language pattern files** — maintain regex sets for each supported
  language. Labor-intensive but precise. Viable for top 10–15 languages.

- **Statistical fallback** — filter any category shared by >60% of all articles
  in the graph. Maintenance categories tend to be universal (e.g., "Articles
  with short description", "Living people" appear on most pages). Language-
  agnostic, less precise but works immediately for any language.

- **Hybrid** (recommended) — statistical filter as the default, with per-language
  override files for the top languages where maintenance category conventions
  are well-understood.

### 6. spaCy NER — Hard

Currently hardcodes `en_core_web_sm`. spaCy has trained NER pipelines for
**25 languages**:

| Language | Model |
|---|---|
| English | `en_core_web_sm` |
| German | `de_core_news_sm` |
| French | `fr_core_news_sm` |
| Spanish | `es_core_news_sm` |
| Japanese | `ja_core_news_sm` |
| Chinese | `zh_core_web_sm` |
| Russian | `ru_core_news_sm` |
| Arabic | `ar_core_news_sm` |
| ... | (17 more) |

These cover the top ~20 Wikipedias by article count. Entity labels
(`PERSON`, `ORG`, `GPE`, `EVENT`) are fairly standard across models.

For languages without a trained model, fall back to:

- `xx_ent_wiki_sm` — multilingual model trained on Wikipedia data across
  many languages. Lower accuracy but broader coverage.
- **Skip NER entirely** — graphs still work without entity helper nodes.
  Wikilink and category edges are language-agnostic.

**Implementation:** A language→model lookup table. User configures the wiki
language; the pipeline loads the corresponding spaCy model (or falls back).

### 7. Topic clustering — Hard

The `TOPIC_KEYWORDS` dict in `clustering.py` is 100% English:

```python
"Sports": {"sport", "athlete", "mma", "ufc", "football", "soccer", ...},
"Music": {"singer", "song", "album", "musician", "band", ...},
"Film & TV": {"film", "movie", "actor", "actress", "television", ...},
```

These words are meaningless in Japanese, Arabic, or Russian. Porting to another
language requires rewriting the entire keyword set in that language — a
significant effort for each supported language.

**Approaches:**

- **Wikidata-based clustering** (recommended long-term) — instead of keyword
  matching, use Wikidata properties:
  - P106 (occupation) → maps to cluster
  - P641 (sport) → Sports
  - P136 (genre) → Music / Film & TV
  - P31 (instance of) → general classification
  - P101 (field of work) → Science & Nature / Technology

  This is language-agnostic, more accurate, and solves the problem permanently
  for all languages. The trade-off: adds Wikidata query dependency to the
  pipeline.

- **Per-language keyword sets** — community-contributed for supported languages.
  Viable for top 10–15 languages but won't scale to 300+.

- **English loanwords as first pass** — English keywords still match loanwords
  in many European languages (e.g., "sport", "film", "music" appear in dozens
  of languages). Adequate as a temporary measure while Wikidata clustering is
  built.

### 8. UI i18n — Hard but optional

All labels, buttons, help text, and error messages are hardcoded in English.
The core functionality can work with English UI for any language's data —
the graph titles, extracts, and category names will be in the target language
regardless.

A proper i18n layer (message catalog per language, RTL support for Arabic
and Hebrew, locale-aware number formatting) would be needed for a polished
multi-language UX but is not required for functional multi-language support.

---

## Recommended implementation order

1. **Add `wiki` parameter** — `?wiki=fr` or `?wiki=de` in URL, wiki selector
   in UI. Swap MW API hostname + Hatnote language code immediately.

2. **Statistical category filter** — language-agnostic fallback that removes
   maintenance categories in any language.

3. **spaCy model selection** — language→model lookup table with `xx_ent_wiki_sm`
   fallback for uncovered languages.

4. **Wikidata-based clustering** — replaces English keywords with language-
   agnostic property-based classification. Solves the hardest problem
   permanently.

5. **UI i18n** — message catalogs and RTL support. Last, because the tool
   is functional without it.

---

## Languages at a glance

| Tier | Languages | NER | Category filter | Clustering |
|---|---|---|---|---|
| 1 (full) | en, de, fr, es, ja, zh, ru, ar, pt, it, nl, pl | spaCy model | Per-language patterns | Wikidata or per-lang keywords |
| 2 (partial) | 15 more with spaCy models | spaCy model | Statistical | Wikidata or English keywords |
| 3 (basic) | All 300+ Wikipedias | `xx_ent_wiki_sm` or skip | Statistical | Wikidata or English keywords |
