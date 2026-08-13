import json
import time
from pathlib import Path
from app.readers.status_reader import read_status
from app.readers.git_reader import read_git_log
from app.readers.constitution_reader import read_constitution
from app.readers.aggregator import aggregate_workspace


def test_read_status_empty_when_missing(monkeypatch):
    from app.readers import status_reader as sr
    monkeypatch.setattr(sr.config, "STATUS_PATH", Path("/nonexistent/status.md"))
    assert read_status() == []


def test_read_status_parses_active_project(tmp_path, monkeypatch):
    from app.readers import status_reader as sr
    status_md = tmp_path / "STATUS.md"
    status_md.write_text("""## 进行中
| 项目 | 当前状态 | 下一步 | 阻塞 |
|------|----------|--------|------|
| **TestProject** | Phase 1 | 继续开发 | 无 |
""", encoding="utf-8")
    monkeypatch.setattr(sr.config, "STATUS_PATH", status_md)
    result = read_status()
    assert len(result) == 1
    assert result[0]["name"] == "TestProject"
    assert result[0]["status"] == "active"


def test_read_git_log_returns_empty_for_missing_project():
    result = read_git_log("___nonexistent___", limit=3)
    assert result == []


def test_read_constitution_returns_files(tmp_path, monkeypatch):
    from app.readers import constitution_reader as cr
    products = tmp_path / "products" / "TestProj"
    const_dir = products / ".context" / "constitution"
    const_dir.mkdir(parents=True)
    (const_dir / "architecture.md").touch()
    (const_dir / "decisions.md").touch()
    monkeypatch.setattr(cr.config, "PRODUCTS_DIR", products.parent)
    files = read_constitution("TestProj")
    assert "architecture.md" in files
    assert "decisions.md" in files


def test_aggregate_workspace_returns_dict(tmp_path, monkeypatch):
    from app.readers import status_reader as sr_mod
    status_md = tmp_path / "STATUS.md"
    status_md.write_text("""## 进行中
| 项目 | 当前状态 | 下一步 | 阻塞 |
|------|----------|--------|------|
| **Test** | P1 | next | 无 |
""", encoding="utf-8")
    monkeypatch.setattr(sr_mod.config, "STATUS_PATH", status_md)
    monkeypatch.setattr(sr_mod.config, "PRODUCTS_DIR", tmp_path / "products")
    (tmp_path / "products" / "Test" / ".context" / "constitution").mkdir(parents=True)
    result = aggregate_workspace()
    assert result["total_projects"] == 1
    assert result["active"] == 1


def test_read_claude_sessions_empty(tmp_path, monkeypatch):
    from app.readers import claude_sessions_reader as csr
    monkeypatch.setattr(csr.Path, "home", lambda: tmp_path)
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    assert csr.read_claude_sessions() == []


def test_read_claude_sessions_extracts_across_projects(tmp_path, monkeypatch):
    from app.readers import claude_sessions_reader as csr
    home = tmp_path / "fakehome"
    home.mkdir()
    proj_a = home / ".claude" / "projects" / "C--Users-16008-foo"
    proj_b = home / ".claude" / "projects" / "-home-me-bar"
    proj_a.mkdir(parents=True)
    proj_b.mkdir(parents=True)

    # session in project A
    s1 = proj_a / "aaa.jsonl"
    s1.write_text(json.dumps({"message": {"role": "user", "content": "Fix the bug"}}) + "\n", encoding="utf-8")
    s1_time = s1.stat().st_mtime

    # session in project B (older)
    s2 = proj_b / "bbb.jsonl"
    s2.write_text(json.dumps({"message": {"role": "user", "content": "Deploy to prod"}}) + "\n", encoding="utf-8")
    time.sleep(0.1)

    monkeypatch.setattr(csr.Path, "home", lambda: home)
    sessions = csr.read_claude_sessions()
    assert len(sessions) == 2
    assert sessions[0]["title"] == "Deploy to prod"
    assert sessions[0]["project_dir"] == "-home-me-bar"
    assert sessions[0]["project_label"] == "me/bar"
    assert sessions[1]["title"] == "Fix the bug"
    assert sessions[1]["project_dir"] == "C--Users-16008-foo"
    assert sessions[1]["project_label"] == "16008/foo"


def test_read_claude_sessions_skips_non_user_messages(tmp_path, monkeypatch):
    from app.readers import claude_sessions_reader as csr
    home = tmp_path / "fakehome"
    home.mkdir()
    proj = home / ".claude" / "projects" / "-test"
    proj.mkdir(parents=True)
    s = proj / "ccc.jsonl"
    s.write_text(
        json.dumps({"message": {"role": "assistant", "content": "Hello"}}) + "\n"
        + json.dumps({"message": {"role": "user", "content": "Real title"}}) + "\n",
        encoding="utf-8"
    )
    monkeypatch.setattr(csr.Path, "home", lambda: home)
    sessions = csr.read_claude_sessions()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Real title"
