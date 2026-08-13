import tempfile
from pathlib import Path
from app.executors.project_init import init_project
from app.executors.file_executor import read_file, write_file


def test_init_project_creates_structure(tmp_path, monkeypatch):
    import app.config as cfg
    products = tmp_path / "products"
    products.mkdir()
    ctx_dir = tmp_path / ".context" / "constitution"
    ctx_dir.mkdir(parents=True)
    (ctx_dir / "architecture.md").write_text("├── products/\n", encoding="utf-8")
    monkeypatch.setattr(cfg.config, "PRODUCTS_DIR", products)
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    result = init_project("TestNew", "product", "a test project")
    assert result["status"] == "created"
    assert (products / "TestNew" / ".context" / "constitution" / "architecture.md").exists()
    assert (products / "TestNew" / ".context" / "constitution" / "decisions.md").exists()
    assert (products / "TestNew" / ".context" / "constitution" / "tech-stack.md").exists()


def test_write_and_read_file(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    result = write_file("test.txt", "hello world")
    assert result["status"] == "written"

    content = read_file("test.txt")
    assert content == "hello world"


def test_read_nonexistent_file(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    content = read_file("no-such-file.xyz")
    assert content == "[file not found]"


def test_write_path_sanitization(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    result = write_file("../outside.txt", "bad")
    assert result["status"] == "error"
    assert "outside" in result["reason"]
