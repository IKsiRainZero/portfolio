from __future__ import annotations
from unittest.mock import patch, MagicMock
from services.pipeline.search import SearchStep, search_web, is_search_available
from services.pipeline.types import StepInput

MOCK_SERPAPI_RESPONSE = {
    "organic_results": [
        {"link": "https://a.com/1", "title": "Serp Result 1", "snippet": "Snippet 1"},
        {"link": "https://b.com/2", "title": "Serp Result 2", "snippet": "Snippet 2"},
    ]
}

MOCK_BRAVE_RESPONSE = {
    "web": {
        "results": [
            {"url": "https://a.com/1", "title": "Brave Result 1", "description": "Desc 1"},
            {"url": "https://b.com/2", "title": "Brave Result 2", "description": "Desc 2"},
        ]
    }
}


# ── SerpAPI (primary) ──

@patch("services.pipeline.search.SERPAPI_KEY", "test_serp_key")
@patch("services.pipeline.search.BRAVE_API_KEY", "")
@patch("services.pipeline.search.requests.get")
def test_search_web_serpapi_returns_results(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_SERPAPI_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    results = search_web("transformer attention", max_results=5)
    assert len(results) == 2
    assert results[0]["url"] == "https://a.com/1"
    assert results[0]["title"] == "Serp Result 1"


@patch("services.pipeline.search.SERPAPI_KEY", "test_serp_key")
@patch("services.pipeline.search.requests.get")
def test_search_web_serpapi_handles_errors(mock_get):
    mock_get.side_effect = Exception("Network error")
    results = search_web("test")
    assert results == []


# ── Brave fallback ──

@patch("services.pipeline.search.SERPAPI_KEY", "")
@patch("services.pipeline.search.BRAVE_API_KEY", "test_brave_key")
@patch("services.pipeline.search.requests.get")
def test_search_web_brave_fallback(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_BRAVE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    results = search_web("transformer", max_results=5)
    assert len(results) == 2
    assert results[0]["title"] == "Brave Result 1"


@patch("services.pipeline.search.SERPAPI_KEY", "")
@patch("services.pipeline.search.BRAVE_API_KEY", "")
def test_search_web_no_keys_returns_empty():
    results = search_web("test")
    assert results == []
    assert not is_search_available()


# ── Step protocol ──

@patch("services.pipeline.search.search_web")
def test_search_step_as_step(mock_search):
    mock_search.return_value = [
        {"url": "https://x.com", "title": "X", "snippet": "..."}
    ]
    step = SearchStep(name="S3_search")
    output = step.run(StepInput(query="transformer", config={"max_results": 5}))
    assert output.status == "ok"
    assert len(output.data["results"]) == 1
    assert output.data["count"] == 1


@patch("services.pipeline.search.is_search_available")
@patch("services.pipeline.search.search_web")
def test_search_step_no_api_key_warns(mock_search, mock_available):
    mock_search.return_value = []
    mock_available.return_value = False
    step = SearchStep(name="S3_search")
    output = step.run(StepInput(query="transformer", config={"max_results": 5}))
    assert output.status == "ok"
    assert "warning" in output.data
    assert output.data["count"] == 0
