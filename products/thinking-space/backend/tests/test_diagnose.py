from unittest.mock import patch, AsyncMock
import json


def test_diagnose_endpoint_accepts_request(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = json.dumps({
        "relation": "测试关系",
        "gaps": ["缺口1"],
        "suggestions": ["建议1"],
        "new_questions": ["问题1"],
    })

    with patch("app.services.diagnosis.AsyncOpenAI") as mock_client:
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        response = client.post("/api/diagnose", json={"question": "测试问题", "dimension_id": dim_id})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: layer_start" in body
        assert "event: layer_complete" in body
        assert "event: diagnose_end" in body


def test_diagnose_invalid_dimension(client):
    with patch("app.services.diagnosis.AsyncOpenAI"):
        response = client.post("/api/diagnose", json={"question": "测试", "dimension_id": "nonexistent"})
        assert response.status_code == 200
        assert "event: error" in response.text
