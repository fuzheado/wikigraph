"""Hatnote API data source — fetches the daily top 100 Wikipedia articles.

Filters out non-article pages (Special:, Wikipedia:, Talk:, etc.).
Results are cached for 24 hours.
"""
import time
import httpx

from ..config import HEADERS, HATNOTE_CACHE_TTL, get_hatnote_url
from ..cache import _cache_get, _cache_set


SKIP_PREFIXES = {"Special", "Wikipedia", "Talk", "User", "Help", "File", "Template",
                 "Category", "Portal", "Draft", "Module", "MediaWiki"}


def fetch_json(url, max_retries=2):
    """Fetch and parse JSON from a URL with a timeout, user-agent, and retries."""
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(headers=HEADERS, timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise  # Don't retry 404s — the resource doesn't exist
            if attempt < max_retries:
                time.sleep(0.5)
            else:
                raise
        except Exception:
            if attempt < max_retries:
                time.sleep(0.5)
            else:
                raise


def fetch_top100(year, month, day, wiki="en"):
    """Fetch the top 100 list from the Hatnote API (cached for 24h).

    Filters out Special:, Wikipedia:, Talk:, and other non-article pages.
    Returns a list of dicts with id, title, rank, views, summary, image_url, url.
    Article IDs use underscores (matching Wikipedia URL convention).
    Accepts an optional wiki language code for multi-language support.
    """
    cache_key = f"{wiki}-{year}-{month}-{day}.json"
    cached = _cache_get("hatnote", cache_key, HATNOTE_CACHE_TTL)
    if cached is not None:
        return cached

    url = get_hatnote_url(year, month, day, wiki)
    try:
        data = fetch_json(url)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(f"No Hatnote data for {year}/{month}/{day}") from None
        raise
    articles = []
    for a in data["articles"]:
        title = a["article"]
        prefix = title.split(":")[0]
        if prefix in SKIP_PREFIXES or title == "Main_Page":
            continue
        articles.append({
            "id": title.replace(" ", "_"),
            "title": a["title"],
            "rank": a["rank"],
            "views": a["views"],
            "summary": a.get("summary", ""),
            "image_url": a.get("image_url", ""),
            "url": a.get("url", f"https://en.wikipedia.org/wiki/{title}"),
            "history": a.get("history", []),
        })

    _cache_set("hatnote", cache_key, articles)
    return articles
