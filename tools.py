"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Default Groq chat model used by the LLM-backed tools.
_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Filter by size (case-insensitive) and max_price.
    candidates = []
    for listing in listings:
        if max_price is not None and listing.get("price", 0) > max_price:
            continue
        if size is not None and not _size_matches(size, listing.get("size", "")):
            continue
        candidates.append(listing)

    # 2. Score each candidate by keyword overlap with the description.
    query_tokens = _tokenize(description)
    scored = []
    for listing in candidates:
        score = _relevance_score(query_tokens, listing)
        if score > 0:
            scored.append((score, listing))

    # 3. Sort by score (highest first) and return the top 3 listings.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored[:3]]


# ── search_listings helpers ─────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase a string and split it into a set of alphanumeric word tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _size_matches(query_size: str, listing_size: str) -> bool:
    """
    Case-insensitive size match. The query size matches if it equals the
    listing size or appears as one of its tokens (e.g. "M" matches "S/M").
    """
    query = query_size.strip().lower()
    listing = listing_size.strip().lower()
    if not query:
        return True
    if query == listing:
        return True
    return query in re.split(r"[^a-z0-9]+", listing)


def _relevance_score(query_tokens: set[str], listing: dict) -> int:
    """
    Score a listing by how many query tokens overlap its searchable text
    (title, description, and style tags), with style tags weighted higher.
    """
    text_tokens = _tokenize(
        f"{listing.get('title', '')} {listing.get('description', '')}"
    )
    tag_tokens = _tokenize(" ".join(listing.get("style_tags", [])))

    text_overlap = len(query_tokens & text_tokens)
    tag_overlap = len(query_tokens & tag_tokens)
    return text_overlap + 2 * tag_overlap


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_desc = _format_item(new_item)
    items = (wardrobe or {}).get("items") or []

    if not items:
        # Empty/minimal wardrobe: offer general styling advice instead of crashing.
        system_prompt = (
            "You are FitFindr, a sharp, friendly personal stylist. The user is "
            "considering a thrifted item but hasn't shared their wardrobe yet. "
            "Give general styling advice: what kinds of pieces pair well with it, "
            "what vibe it suits, and 1-2 example outfit directions. Be concrete "
            "and concise."
        )
        user_prompt = f"Item I'm considering:\n{item_desc}"
    else:
        wardrobe_desc = "\n".join(f"- {_format_item(i)}" for i in items)
        system_prompt = (
            "You are FitFindr, a sharp, friendly personal stylist. Suggest 1-2 "
            "complete outfit combinations that pair the new item with specific, "
            "named pieces from the user's wardrobe. Only use pieces that are "
            "actually listed. For each outfit, name the pieces and briefly explain "
            "why it works. If nothing in the wardrobe pairs well, say so honestly."
        )
        user_prompt = (
            f"New item:\n{item_desc}\n\n"
            f"My wardrobe:\n{wardrobe_desc}"
        )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def _format_item(item: dict) -> str:
    """Render a listing/wardrobe item as a compact one-line description."""
    name = item.get("name") or item.get("title") or "item"
    parts = [name]
    if item.get("category"):
        parts.append(f"category: {item['category']}")
    if item.get("colors"):
        parts.append(f"colors: {', '.join(item['colors'])}")
    if item.get("style_tags"):
        parts.append(f"style: {', '.join(item['style_tags'])}")
    if item.get("notes"):
        parts.append(f"notes: {item['notes']}")
    return " | ".join(parts)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty or whitespace-only outfit.
    if not outfit or not str(outfit).strip():
        return "Can't write a caption without an outfit — run suggest_outfit first."

    item_desc = _format_item(new_item)
    price = new_item.get("price")
    platform = new_item.get("platform")
    item_name = new_item.get("name") or new_item.get("title") or "the piece"

    details = [f"Item: {item_desc}"]
    if price is not None:
        details.append(f"Price: ${price}")
    if platform:
        details.append(f"Platform: {platform}")
    details.append(f"Outfit: {str(outfit).strip()}")

    system_prompt = (
        "You are FitFindr, writing a caption for a thrifted-outfit post. "
        "Write a casual, authentic OOTD caption (2-4 sentences) — like a real "
        "person posting their find, not a product description. Capture the "
        "outfit's vibe in specific terms. Mention the item name, its price, and "
        "the platform it's from naturally, once each. A tasteful emoji or two is "
        "fine. Output only the caption."
    )
    user_prompt = (
        f"{chr(10).join(details)}\n\n"
        f"Write the caption for \"{item_name}\"."
    )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # Higher temperature so captions vary across runs/inputs.
        temperature=1.0,
    )
    return response.choices[0].message.content.strip()
