"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parsing ───────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract a search description, optional size, and optional max_price from a
    natural language query using regex/string cleanup.

    Examples:
        "vintage graphic tee under $30, size M"
            → {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}
        "baggy denim jeans size W30 L30 less than 50 dollars"
            → {"description": "baggy denim jeans", "size": "W30 L30", "max_price": 50.0}
    """
    text = query.strip()
    description = text

    # max_price: anchor on a price cue word or a $ sign so we don't grab a size
    # number (e.g. the "30" in "W30"). "under $30", "less than 50", "$25".
    max_price = None
    cue_match = re.search(
        r"(?:under|below|less than|max|up to|<=?|\$)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|usd|bucks)?",
        text,
        re.IGNORECASE,
    )
    if cue_match:
        max_price = float(cue_match.group(1))
        description = description.replace(cue_match.group(0), " ")

    # size: "size M", "size XXS", or a waist/length pair "size W30 L30".
    size = None
    size_match = re.search(
        r"\bsize\s+(W\d+\s+L\d+|[A-Za-z0-9/]+)",
        text,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1).strip()
        description = description.replace(size_match.group(0), " ")

    # Clean leftover filler/punctuation from the description.
    description = re.sub(
        r"\b(?:i'?m\s+looking\s+for|looking\s+for|i\s+want|i\s+need|find\s+me|show\s+me|a|an|the)\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"[,;]+", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into description / size / max_price.
    session["parsed"] = _parse_query(query)
    parsed = session["parsed"]

    # Step 3: search listings. Stop early if nothing matches.
    try:
        session["search_results"] = search_listings(
            description=parsed["description"],
            size=parsed["size"],
            max_price=parsed["max_price"],
        )
    except Exception as exc:  # tool failure → stop and help the user debug.
        session["error"] = f"search_listings failed: {exc}"
        return session

    if not session["search_results"]:
        session["error"] = (
            "No listings matched that search. Try loosening the size, raising "
            "the max price, or using different keywords."
        )
        return session

    # Step 4: select the top (most relevant) result.
    session["selected_item"] = session["search_results"][0]

    # Step 5: suggest an outfit using the selected item + wardrobe.
    try:
        session["outfit_suggestion"] = suggest_outfit(
            session["selected_item"], wardrobe
        )
    except Exception as exc:
        session["error"] = f"suggest_outfit failed: {exc}"
        return session

    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = "Couldn't generate an outfit suggestion for that item."
        return session

    # Step 6: turn the outfit into a shareable fit card.
    try:
        session["fit_card"] = create_fit_card(
            session["outfit_suggestion"], session["selected_item"]
        )
    except Exception as exc:
        session["error"] = f"create_fit_card failed: {exc}"
        return session

    # Step 7: done.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="XXS designer ballgown for less than $5",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
