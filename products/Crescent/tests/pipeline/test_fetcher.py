from __future__ import annotations
from unittest.mock import patch, MagicMock
from services.pipeline.fetcher import fetch_url, FetchStep
from services.pipeline.types import StepInput

RAW_HTML = "<html><head><title>Test Page</title></head><body><p>Hello world.</p></body></html>"


@patch("services.pipeline.fetcher.requests.get")
def test_fetch_url_returns_text(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = RAW_HTML
    mock_resp.raise_status.return_value = None
    mock_get.return_value = mock_resp

    text = fetch_url("https://example.com")
    assert "Hello world" in text


@patch("services.pipeline.fetcher.requests.get")
def test_fetch_url_timeout_returns_none(mock_get):
    import requests as r
    mock_get.side_effect = r.exceptions.Timeout()
    assert fetch_url("https://slow.com", timeout=3) is None


@patch("services.pipeline.fetcher.fetch_url")
def test_fetch_step(mock_fetch):
    mock_fetch.return_value = RAW_HTML
    step = FetchStep(name="S3_fetch")
    input = StepInput(
        query="test",
        previous_outputs={"S3_search": {"results": [{"url": "https://a.com", "title": "A"}]}},
    )
    output = step.run(input)
    assert output.status == "ok"
    assert len(output.data["documents"]) == 1
