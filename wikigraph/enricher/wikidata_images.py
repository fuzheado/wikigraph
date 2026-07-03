"""Wikidata image enrichment — batch fetch P18 (image) for article Wikidata items.

Queries the Wikidata API for P18 claims in batches, then resolves the
Commons filenames to browser-accessible thumbnail URLs. Results are cached
for 7 days since Wikidata P18 images rarely change.

Usage:
    images = fetch_wikidata_images(["Q11660", "Q42", "Q76"])
    # → {"Q11660": "https://upload.wikimedia.org/...", "Q42": "", ...}
"""
import re
import time
from urllib.parse import quote

import httpx

from ..config import HEADERS

# Commons file URL base for direct access
COMMONS_THUMB_BASE = "https://upload.wikimedia.org/wikipedia/commons/thumb"
COMMONS_FILE_BASE = "https://commons.wikimedia.org/wiki/Special:FilePath"

# Maximum QIDs per batch request
BATCH_SIZE = 50

# Cache TTL for Wikidata image lookups (7 days — images rarely change)
WD_IMAGE_CACHE_TTL = 604800


def _commons_filename_to_url(filename, thumb_width=300):
    """Convert a Commons filename (e.g. 'File:Example.jpg') to a thumbnail URL.

    Uses the Wikimedia upload.wikimedia.org URL scheme:
    https://upload.wikimedia.org/wikipedia/commons/thumb/{hash}/{filename}/{width}px-{filename}
    """
    # Strip File: prefix if present
    name = filename
    if name.startswith("File:"):
        name = name[5:]
    if name.startswith("Image:"):
        name = name[6:]

    name = name.strip()

    # Compute the hash path (first char, first two chars)
    # Wikimedia uses MD5 first character / first two characters
    import hashlib
    m = hashlib.md5(name.encode("utf-8"))
    hash_hex = m.hexdigest()

    # URL-encode spaces as underscores
    safe_name = name.replace(" ", "_")

    # Build the thumbnail URL
    url = f"{COMMONS_THUMB_BASE}/{hash_hex[0]}/{hash_hex[0:2]}/{quote(safe_name)}/{thumb_width}px-{quote(safe_name)}"
    return url


def _extract_p18_from_entity(entity):
    """Extract the P18 image filename from a Wikidata entity claims dict.

    Returns empty string if no valid P18 claim exists.
    """
    claims = entity.get("claims", {})
    p18_claims = claims.get("P18", [])
    for claim in p18_claims:
        mainsnak = claim.get("mainsnak", {})
        if mainsnak.get("snaktype") != "value":
            continue
        datavalue = mainsnak.get("datavalue", {})
        if datavalue.get("type") == "string":
            return datavalue.get("value", "")
    return ""


def fetch_wikidata_images(qids, headers=None):
    """Fetch P18 (image) URLs for a list of Wikidata QIDs.

    Batches requests (50 QIDs at a time) to the Wikidata API.
    Results are cached for 7 days to avoid redundant API calls.
    Returns a dict mapping QID → thumbnail URL (or empty string).

    Args:
        qids: list of Wikidata QID strings (e.g. ["Q42", "Q76"])
        headers: optional HTTP headers dict

    Returns:
        dict: {qid: thumbnail_url_or_empty}
    """
    from ..cache import _cache_get, _cache_set

    if not qids:
        return {}

    result = {}
    hdrs = dict(headers or HEADERS)

    # Remove wikibase_item entries that are empty
    valid_qids = [q for q in qids if q and q.startswith("Q")]
    if not valid_qids:
        return {}

    # Check cache first
    uncached_qids = []
    for qid in valid_qids:
        cache_key = f"wd_img_{qid}.json"
        cached = _cache_get("mw", cache_key, WD_IMAGE_CACHE_TTL)
        if cached is not None:
            result[qid] = cached
        else:
            uncached_qids.append(qid)

    if not uncached_qids:
        return result

    # Fetch uncached QIDs from Wikidata API in batches
    with httpx.Client(headers=hdrs, timeout=30.0) as client:
        for i in range(0, len(uncached_qids), BATCH_SIZE):
            batch = uncached_qids[i:i + BATCH_SIZE]
            ids = "|".join(batch)

            params = {
                "action": "wbgetentities",
                "ids": ids,
                "props": "claims",
                "format": "json",
            }

            for attempt in range(3):
                try:
                    resp = client.get(
                        "https://www.wikidata.org/w/api.php",
                        params=params,
                        timeout=15.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    entities = data.get("entities", {})
                    for qid, entity in entities.items():
                        filename = _extract_p18_from_entity(entity)
                        if filename:
                            url = _commons_filename_to_url(filename)
                            result[qid] = url
                        else:
                            result[qid] = ""
                        # Cache individual result
                        _cache_set("mw", f"wd_img_{qid}.json", result[qid])

                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(0.5 * (2 ** attempt))
                    else:
                        print(f"  Wikidata image fetch failed for batch: {e}")
                        for qid in batch:
                            result[qid] = ""

    return result


def fetch_wikidata_images_batch(qids, headers=None):
    """Alias for fetch_wikidata_images()."""
    return fetch_wikidata_images(qids, headers=headers)
