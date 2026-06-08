"""
Tests for the three FitFindr tools in tools.py.

The LLM-backed tools (suggest_outfit, create_fit_card) are tested against a
fake Groq client so the suite is deterministic and makes no network calls.
The fake records the prompts it receives so we can assert on tool behavior.
"""

import pytest

import tools


# ── Fake Groq client ─────────────────────────────────────────────────────────

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    """Records every chat.completions.create call and returns canned content."""

    def __init__(self, content="canned LLM reply"):
        self._content = content
        self.calls = []
        self.chat = self  # so client.chat.completions resolves to self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._content)


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch tools._get_groq_client to return a recording fake client."""
    client = _FakeClient()
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)
    return client


# ── Tool 1: search_listings ──────────────────────────────────────────────────

def test_search_returns_empty_when_nothing_matches():
    # Failure mode: no relevant matches → returns [] (does not raise).
    results = tools.search_listings("zzzznomatchquery", max_price=10000)
    assert results == []


def test_search_respects_max_price():
    # Failure mode: price ceiling excludes too-expensive listings.
    results = tools.search_listings("jeans denim vintage", max_price=20.0)
    assert results, "expected at least one cheap match"
    assert all(item["price"] <= 20.0 for item in results)


def test_search_filters_by_size_case_insensitively():
    # Failure mode: size filter must drop non-matching sizes (case-insensitive).
    results = tools.search_listings("jeans denim", size="w30 l30")
    assert results, "expected a W30 L30 match despite lowercase query"
    assert all(item["size"].lower() == "w30 l30" for item in results)


def test_search_returns_at_most_three_sorted_by_relevance():
    # Failure mode: must cap at top 3 and order by decreasing relevance.
    results = tools.search_listings("vintage", max_price=10000)
    assert len(results) <= 3

    # Recompute scores and confirm non-increasing order.
    query_tokens = tools._tokenize("vintage")
    scores = [tools._relevance_score(query_tokens, item) for item in results]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    assert all(s > 0 for s in scores), "zero-score listings must be dropped"


def test_search_size_mismatch_excludes_everything():
    # Failure mode: a size present in no listing yields no results.
    results = tools.search_listings("jeans denim vintage", size="NOPE-999")
    assert results == []


# ── Tool 2: suggest_outfit ───────────────────────────────────────────────────

_NEW_ITEM = {
    "id": "lst_001",
    "name": "Vintage Levi's 501 Jeans",
    "title": "Vintage Levi's 501 Jeans",
    "category": "bottoms",
    "style_tags": ["vintage", "denim", "streetwear"],
    "colors": ["blue", "indigo"],
    "price": 38.0,
    "platform": "depop",
}

_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "White ribbed tank top",
            "category": "tops",
            "colors": ["white"],
            "style_tags": ["basic", "minimal"],
        },
        {
            "id": "w_002",
            "name": "Black combat boots",
            "category": "shoes",
            "colors": ["black"],
            "style_tags": ["edgy"],
        },
    ]
}


def test_suggest_outfit_uses_named_wardrobe_pieces(fake_llm):
    result = tools.suggest_outfit(_NEW_ITEM, _WARDROBE)
    assert isinstance(result, str) and result.strip()

    # The wardrobe items must be passed into the prompt.
    prompt = "".join(m["content"] for m in fake_llm.calls[0]["messages"])
    assert "White ribbed tank top" in prompt
    assert "Black combat boots" in prompt


def test_suggest_outfit_empty_wardrobe_gives_general_advice(fake_llm):
    # Failure mode: empty wardrobe must not crash and must still return advice.
    result = tools.suggest_outfit(_NEW_ITEM, {"items": []})
    assert isinstance(result, str) and result.strip()
    # No wardrobe pieces to reference, so a different (general) prompt is used.
    system_prompt = fake_llm.calls[0]["messages"][0]["content"]
    assert "hasn't shared their wardrobe" in system_prompt


def test_suggest_outfit_handles_none_wardrobe(fake_llm):
    # Failure mode: wardrobe is None / missing 'items' key → no crash.
    result_none = tools.suggest_outfit(_NEW_ITEM, None)
    result_missing = tools.suggest_outfit(_NEW_ITEM, {})
    assert result_none.strip()
    assert result_missing.strip()


# ── Tool 3: create_fit_card ──────────────────────────────────────────────────

_OUTFIT = (
    "Vintage Levi's 501 Jeans with a white ribbed tank and black combat boots."
)


def test_create_fit_card_returns_caption(fake_llm):
    result = tools.create_fit_card(_OUTFIT, _NEW_ITEM)
    assert isinstance(result, str) and result.strip()

    # Item name, price, and platform should be supplied to the LLM.
    prompt = "".join(m["content"] for m in fake_llm.calls[0]["messages"])
    assert "Vintage Levi's 501 Jeans" in prompt
    assert "38.0" in prompt
    assert "depop" in prompt


def test_create_fit_card_uses_high_temperature(fake_llm):
    # Captions must vary → tool should request a high temperature.
    tools.create_fit_card(_OUTFIT, _NEW_ITEM)
    assert fake_llm.calls[0]["temperature"] >= 0.9


def test_create_fit_card_empty_outfit_is_guarded(fake_llm):
    # Failure mode: empty / whitespace outfit returns a guard message,
    # never calls the LLM, and never raises.
    for bad in ("", "   ", None):
        result = tools.create_fit_card(bad, _NEW_ITEM)
        assert isinstance(result, str) and result.strip()
    assert fake_llm.calls == [], "LLM must not be called for an empty outfit"
