"""Configuration management via environment variables and .env file.

Loads settings at module import time. All constants are available for
direct import by other modules.
"""
import os
import re
from pathlib import Path

def _load_dotenv():
    """Load .env file if present, populating os.environ (does not override)."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            os.environ.setdefault(key, val)

def _is_valid_ua(ua):
    """Check if a User-Agent string appears Wikimedia-compliant (has contact info).

    Wikimedia requires User-Agent strings to include a way to contact the
    developer — either an email address or a project URL. Returns True if
    the string contains an email or http(s) URL.
    """
    return bool(re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+|https?://\S+', ua))

# Load .env at import time (matches original build_graph.py behaviour)
_load_dotenv()

# ── Multi-language support ──────────────────────────────────

# Language code → wiki hostname for supported Wikipedias
WIKI_LANGUAGES = {
    "ar": "ar.wikipedia.org",
    "de": "de.wikipedia.org",
    "en": "en.wikipedia.org",
    "es": "es.wikipedia.org",
    "fr": "fr.wikipedia.org",
    "it": "it.wikipedia.org",
    "ja": "ja.wikipedia.org",
    "nl": "nl.wikipedia.org",
    "pl": "pl.wikipedia.org",
    "pt": "pt.wikipedia.org",
    "ru": "ru.wikipedia.org",
    "zh": "zh.wikipedia.org",
}


def get_wiki_host(wiki="en"):
    """Get the MediaWiki hostname for a language code, defaulting to English."""
    return WIKI_LANGUAGES.get(wiki, "en.wikipedia.org")


def get_mw_api(wiki="en"):
    """Get the MediaWiki API URL for a language code."""
    return f"https://{get_wiki_host(wiki)}/w/api.php"


def get_hatnote_url(year, month, day, wiki="en"):
    """Get the Hatnote top-100 URL for a language code and date."""
    lang = wiki.split("-")[0]  # Handle "zh-cn" etc.
    return f"https://top.hatnote.com/{lang}/wikipedia/{year}/{month}/{day}.json"


# ── Legacy module-level constants ────────────────────────────

HATNOTE_URL = os.environ.get("WIKI_HATNOTE_URL",
    "https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json")
MW_API = os.environ.get("WIKI_MW_API",
    "https://en.wikipedia.org/w/api.php")
_DEFAULT_UA = "WikiTop100Viz/1.0 (contact: andrew.lih@gmail.com)"
HEADERS = {"User-Agent": os.environ.get("WIKI_USER_AGENT", _DEFAULT_UA)}
MAX_CONCURRENT = int(os.environ.get("WIKI_MAX_CONCURRENT", "3"))
CACHE_DIR = os.environ.get("WIKI_CACHE_DIR", ".cache")
HATNOTE_CACHE_TTL = int(os.environ.get("WIKI_HATNOTE_CACHE_TTL", "86400"))  # 24h
MW_CACHE_TTL = int(os.environ.get("WIKI_MW_CACHE_TTL", "604800"))  # 7d


# ── spaCy model selection ────────────────────────────────────

# Language code → spaCy NER model name for supported languages
SPACY_MODELS = {
    "ar": "ar_core_news_sm",
    "de": "de_core_news_sm",
    "en": "en_core_web_sm",
    "es": "es_core_news_sm",
    "fr": "fr_core_news_sm",
    "it": "it_core_news_sm",
    "ja": "ja_core_news_sm",
    "nl": "nl_core_news_sm",
    "pl": "pl_core_news_sm",
    "pt": "pt_core_news_sm",
    "ru": "ru_core_news_sm",
    "zh": "zh_core_web_sm",
}
# Multilingual fallback model (lower accuracy, broader coverage)
SPACY_FALLBACK_MODEL = "xx_ent_wiki_sm"


def get_spacy_model(wiki="en"):
    """Get the spaCy NER model name for a language code.

    Returns the language-specific model if available, falls back to
    the multilingual model, or returns None if spaCy has no coverage.
    """
    return SPACY_MODELS.get(wiki, SPACY_FALLBACK_MODEL)
