from app.ai.tools import TOOLS, execute_tool


def test_all_tools_have_required_fields():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert "type" in tool["input_schema"]


def test_tool_count_is_8():
    assert len(TOOLS) == 8


def test_read_project_status_unknown_project():
    result = execute_tool("read_project_status", {"project_name": "___nonexistent___"})
    assert result["name"] == "___nonexistent___" or result.get("status") == "unknown"


def test_unknown_tool_returns_error():
    result = execute_tool("nonexistent_tool", {})
    assert "error" in result


def test_search_knowledge(tmp_path, monkeypatch):
    import app.config as cfg
    ref = tmp_path / ".context" / "reference"
    ref.mkdir(parents=True)
    (ref / "test.md").write_text("this contains a keyword: portfolio", encoding="utf-8")
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    result = execute_tool("search_knowledge", {"query": "portfolio"})
    assert len(result["results"]) > 0
