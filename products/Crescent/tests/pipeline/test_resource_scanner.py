from __future__ import annotations
from unittest.mock import patch, MagicMock
from services.pipeline.resource_scanner import ResourceScannerStep, _scan_l1, _scan_l2
from services.pipeline.types import StepInput


def test_scan_l1_returns_file_summary(tmp_path):
    """tmp_path is a pytest built-in fixture."""
    (tmp_path / "test.md").write_text("# Hello\nWorld", encoding="utf-8")
    (tmp_path / "script.py").write_text("print('hello')", encoding="utf-8")
    result = _scan_l1(str(tmp_path))
    assert result["file_count"] >= 2
    assert any(f["ext"] == ".md" for f in result["files"])
    assert any(f["ext"] == ".py" for f in result["files"])


def test_scan_l1_skips_venv_and_cache(tmp_path):
    """Should skip directories matching known exclusion patterns."""
    project = tmp_path / "project"
    # Create .venv dir with a .py file inside
    venv_dir = project / ".venv"
    venv_dir.mkdir(parents=True, exist_ok=True)
    (venv_dir / "lib.py").write_text("x=1", encoding="utf-8")
    # Create src dir with a .py file inside (should be picked up)
    src_dir = project / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.py").write_text("print(1)", encoding="utf-8")
    result = _scan_l1(str(project))
    assert result["file_count"] == 1
    assert all("lib.py" not in f["path"] for f in result["files"])


def test_scan_l1_ignores_unsupported_extensions(tmp_path):
    """Only extensions in L1_EXTENSIONS should be included."""
    (tmp_path / "data.bin").write_bytes(b"\x00\x01")
    (tmp_path / "notes.md").write_text("note", encoding="utf-8")
    result = _scan_l1(str(tmp_path))
    assert result["file_count"] == 1
    assert result["files"][0]["ext"] == ".md"


def test_scan_l1_empty_directory(tmp_path):
    """Empty dir returns file_count 0 and empty files list."""
    result = _scan_l1(str(tmp_path))
    assert result["file_count"] == 0
    assert result["files"] == []


@patch("services.pipeline.resource_scanner.chat")
def test_scan_l2_extracts_skills(mock_chat):
    import json

    mock_chat.return_value = (json.dumps({
        "skills": ["Python", "FastAPI", "Machine Learning"],
        "projects": [{"name": "Crescent", "status": "active"}],
        "knowledge_areas": ["NLP", "RAG"],
        "assets": [{"type": "codebase", "description": "FastAPI app"}],
        "relations": [],
    }), {"total_tokens": 100})

    file_summaries = [
        {"path": "portfolio/Crescent/app.py", "summary": "FastAPI application entry point"},
        {"path": "portfolio/Crescent/services/rag_service.py", "summary": "RAG retrieval service"},
    ]
    result = _scan_l2(file_summaries)
    assert "Python" in result["skills"]
    assert len(result["projects"]) == 1
    assert "NLP" in result["knowledge_areas"]
    assert result["assets"][0]["type"] == "codebase"


@patch("services.pipeline.resource_scanner.chat")
def test_scan_l2_empty_summaries(mock_chat):
    import json

    mock_chat.return_value = (json.dumps({
        "skills": [], "projects": [], "knowledge_areas": [],
        "assets": [], "relations": [],
    }), {"total_tokens": 0})

    result = _scan_l2([])
    assert result["skills"] == []
    assert result["projects"] == []


@patch("services.pipeline.resource_scanner.chat")
def test_scan_l2_llm_failure_returns_empty(mock_chat):
    """On LLM failure, return empty lists, not crash."""
    mock_chat.side_effect = Exception("API unavailable")

    result = _scan_l2([{"path": "x.py", "summary": "test"}])
    assert result == {"skills": [], "projects": [], "knowledge_areas": [], "assets": [], "relations": []}


@patch("services.pipeline.resource_scanner.chat")
def test_scan_l2_strips_code_fence(mock_chat):
    """Should strip markdown code fences before JSON parsing."""
    mock_chat.return_value = (
        '```json\n{"skills": ["Python"], "projects": [], "knowledge_areas": [], "assets": [], "relations": []}\n```',
        {"total_tokens": 50},
    )

    result = _scan_l2([{"path": "x.py", "summary": "Python file"}])
    assert "Python" in result["skills"]


@patch("services.pipeline.resource_scanner._scan_l1")
@patch("services.pipeline.resource_scanner._scan_l2")
def test_scanner_step(mock_l2, mock_l1, tmp_path):
    # Create a real directory so os.path.isdir passes
    scan_dir = tmp_path / "project"
    scan_dir.mkdir()
    (scan_dir / "main.py").write_text("print(1)", encoding="utf-8")
    # Let _scan_l1 run for real to populate files from the tmp dir
    mock_l1.side_effect = None
    mock_l1.return_value = {"file_count": 1, "files": [
        {"path": str(scan_dir / "main.py"), "name": "main.py", "ext": ".py",
         "size_kb": 0.1, "modified": 0.0},
    ]}
    mock_l2.return_value = {
        "skills": ["Python"], "projects": [], "knowledge_areas": [],
        "assets": [], "relations": [],
    }

    step = ResourceScannerStep(name="S2")
    output = step.run(StepInput(query="test", config={"scan_paths": [str(scan_dir)]}))
    assert output.status == "ok"
    assert "skills" in output.data
    assert "l1_summary" in output.data


def test_scanner_step_no_files(tmp_path):
    """When scan_paths yields no files, step is skipped."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    step = ResourceScannerStep(name="S2")
    output = step.run(StepInput(query="test", config={"scan_paths": [str(empty_dir)]}))
    assert output.status == "skipped"
    assert "reason" in output.data


def test_can_skip_no_scan_paths():
    """can_skip returns True when scan_paths is not in config."""
    step = ResourceScannerStep(name="S2")
    assert step.can_skip(StepInput(query="test", config={})) is True


def test_can_skip_with_scan_paths():
    """can_skip returns False when scan_paths is present."""
    step = ResourceScannerStep(name="S2")
    assert step.can_skip(StepInput(query="test", config={"scan_paths": ["/some/path"]})) is False


def test_can_skip_empty_scan_paths():
    """can_skip returns True when scan_paths is an empty list."""
    step = ResourceScannerStep(name="S2")
    assert step.can_skip(StepInput(query="test", config={"scan_paths": []})) is True
