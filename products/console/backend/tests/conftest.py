import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def portfolio_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # STATUS.md — TestProject active (进行中), DoneProject dormant (休眠)
        (root / "STATUS.md").write_text("""## 进行中
| 项目 | 当前状态 | 下一步 | 阻塞 |
|------|----------|--------|------|
| **TestProject** | Phase 1 | write more tests | pytest not configured |

## 休眠
| 项目 | 当前状态 | 下一步 | 阻塞 |
|------|----------|--------|------|
| **DoneProject** | Phase 5 | none | 无 |
""", encoding="utf-8")
        # Root-level constitution (needed by _update_architecture_manifest)
        (root / ".context" / "constitution").mkdir(parents=True)
        (root / ".context" / "constitution" / "architecture.md").write_text(
            "├── products/\n", encoding="utf-8"
        )
        # TestProject — has architecture.md + decisions.md (2 constitution files, 1 risk)
        (root / "products" / "TestProject" / ".context" / "constitution").mkdir(parents=True)
        (root / "products" / "TestProject" / ".context" / "constitution" / "architecture.md").write_text(
            "TestProject architecture", encoding="utf-8"
        )
        (root / "products" / "TestProject" / ".context" / "constitution" / "decisions.md").touch()
        # DoneProject — only architecture.md (1 constitution file, 0 risks)
        (root / "products" / "DoneProject" / ".context" / "constitution").mkdir(parents=True)
        (root / "products" / "DoneProject" / ".context" / "constitution" / "architecture.md").touch()

        import app.config as cfg
        import app.tracer as tracer_mod
        traces_dir = root / ".context" / "observability" / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        cfg.config.PORTFOLIO_ROOT = root
        cfg.config.STATUS_PATH = root / "STATUS.md"
        cfg.config.PRODUCTS_DIR = root / "products"
        cfg.config.TRACES_DIR = traces_dir
        # Redirect the module-level tracer so traces land in the temp dir
        tracer_mod.get_tracer().traces_dir = traces_dir
        yield root
