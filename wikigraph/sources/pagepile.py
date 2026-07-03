"""PagePile data source — fetches article lists from PagePile IDs.

PagePile (https://pagepile.toolforge.org/) manages lists of wiki pages,
each identified by an integer ID. Lists can be several hundred to tens of
thousands of pages. Results are cached for 24 hours.
"""
import time
import httpx

from ..config import HEADERS

PAGEPILE_URL = "https://pagepile.toolforge.org/api.php"
PAGEPILE_CACHE_TTL = 86400  # 24 hours


def fetch_pagepile(pile_id):
    """Fetch article titles from a PagePile ID.

    Returns a dict with:
      - titles: list of article title strings
      - wiki: wiki identifier (e.g. 'enwiki')
      - total: total page count
      - id: the pile ID

    Raises ValueError for invalid IDs or non-existent piles.
    """
    import json
    import asyncio
    from ..cache import _cache_get, _cache_set

    cache_key = f"pile_{pile_id}.json"
    cached = _cache_get("hatnote", cache_key, PAGEPILE_CACHE_TTL)
    if cached is not None:
        return cached

    # First fetch with metadata to get total count and wiki
    params = {
        "action": "get_data",
        "id": pile_id,
        "format": "json",
        "metadata": "1",
    }

    try:
        with httpx.Client(headers=HEADERS, timeout=30.0) as client:
            resp = client.get(PAGEPILE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"PagePile ID {pile_id} not found or unavailable") from None

    pages = data.get("pages")
    if not pages or not isinstance(pages, dict):
        raise ValueError(f"PagePile ID {pile_id} is empty or invalid")

    titles = sorted(pages.keys())
    result = {
        "titles": titles,
        "wiki": data.get("wiki", ""),
        "total": data.get("pages_returned", len(titles)),
        "id": data.get("id", pile_id),
    }

    _cache_set("hatnote", cache_key, result)
    return result
