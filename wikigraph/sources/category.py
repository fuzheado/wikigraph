"""Category data source — fetches article lists from Wikipedia categories.

Uses the MediaWiki Action API (list=categorymembers) to fetch members
of a category and optionally its subcategories up to a configurable depth.
Results are cached for 24 hours.
"""
import time
import httpx

from ..config import HEADERS, MW_API

CATEGORY_CACHE_TTL = 86400  # 24 hours
MAX_ARTICLES = 500
MAX_DEPTH = 2

# Pages per API request — 'max' for members, 500 for subcats
CM_LIMIT = "max"


def _fetch_members(client, title, cmtype):
    """Fetch all members of a given type from a category title (with pagination).

    Args:
      client: httpx.Client
      title: category title (without 'Category:' prefix)
      cmtype: 'page' for articles, 'subcat' for subcategories

    Returns:
      list of page titles
    """
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{title}",
        "cmtype": cmtype,
        "cmlimit": CM_LIMIT,
        "format": "json",
    }
    while True:
        resp = client.get(MW_API, params=params)
        resp.raise_for_status()
        data = resp.json()
        members = data.get("query", {}).get("categorymembers", [])
        for m in members:
            titles.append(m["title"])
        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break
    return titles


def fetch_category(category_name, depth=0):
    """Fetch article titles from a Wikipedia category.

    Args:
      category_name: category name (e.g. 'Artificial_intelligence' or
                     'Category:Artificial_intelligence')
      depth: recursion depth for subcategories (0-2, default 0)

    Returns:
      dict with titles (list of article title strings), total count,
      depth used, and category name.

    Raises ValueError for invalid category names or empty categories.
    """
    from ..cache import _cache_get, _cache_set

    # Strip 'Category:' prefix if present
    if category_name.startswith("Category:"):
        category_name = category_name[len("Category:"):]

    depth = max(0, min(depth, MAX_DEPTH))

    cache_key = f"cat_{category_name}_d{depth}.json"
    cached = _cache_get("mw", cache_key, CATEGORY_CACHE_TTL)
    if cached is not None:
        return cached

    try:
        with httpx.Client(headers=HEADERS, timeout=30.0) as client:
            # Gather all categories to query (root + subcategories at each level)
            cat_queue = [(category_name, 0)]  # (title, current_depth)
            all_articles = []
            seen_cats = set()

            while cat_queue:
                cat_title, current_depth = cat_queue.pop(0)
                if cat_title in seen_cats:
                    continue
                seen_cats.add(cat_title)

                # Fetch articles from this category
                articles = _fetch_members(client, cat_title, "page")
                all_articles.extend(articles)

                # If more depth needed, fetch subcategories
                if current_depth < depth:
                    subcats = _fetch_members(client, cat_title, "subcat")
                    for sc in subcats:
                        # Strip 'Category:' prefix from subcategory titles
                        sc_name = sc.replace("Category:", "")
                        if sc_name not in seen_cats:
                            cat_queue.append((sc_name, current_depth + 1))

                # Check against max articles cap
                if len(all_articles) >= MAX_ARTICLES:
                    break

            if not all_articles:
                raise ValueError(f"Category '{category_name}' is empty or does not exist")

            # Deduplicate while preserving order
            seen = set()
            unique = []
            for t in all_articles:
                if t not in seen:
                    seen.add(t)
                    unique.append(t)

            if len(unique) > MAX_ARTICLES:
                unique = unique[:MAX_ARTICLES]

            result = {
                "titles": unique,
                "total": len(unique),
                "depth": depth,
                "category": category_name,
            }

            _cache_set("mw", cache_key, result)
            return result

    except httpx.HTTPStatusError as e:
        raise ValueError(f"Failed to fetch category '{category_name}'") from None
    except KeyError:
        raise ValueError(f"Category '{category_name}' not found or inaccessible")
