from pathlib import Path
from ..config import config
from ..tracer import traced


PROJECT_TEMPLATE = """# {name} 项目架构

## 定位
{description}

## 目录结构
```
products/{name}/
├── .context/
│   └── constitution/
└── README.md
```

## 当前状态
项目初始化完成。
"""

DECISIONS_TEMPLATE = """# {name} 关键决策

## ADR-001: 项目创建
- **决策**: 通过 Console 初始化
- **理由**: {description}
"""

TECHSTACK_TEMPLATE = """# {name} 技术栈

## 技术选型
待定。
"""


@traced("project.init")
def init_project(name: str, proj_type: str = "product", description: str = "") -> dict:
    base = config.PRODUCTS_DIR if proj_type == "product" else config.PORTFOLIO_ROOT / proj_type
    project_dir = base / name
    project_dir.mkdir(parents=True, exist_ok=True)

    const_dir = project_dir / ".context" / "constitution"
    sessions_dir = project_dir / ".context" / "sessions" / "archive"
    modules_dir = project_dir / ".context" / "modules"
    for d in [const_dir, sessions_dir, modules_dir]:
        d.mkdir(parents=True, exist_ok=True)

    (const_dir / "architecture.md").write_text(
        PROJECT_TEMPLATE.format(name=name, description=description or "新项目"),
        encoding="utf-8"
    )
    (const_dir / "decisions.md").write_text(
        DECISIONS_TEMPLATE.format(name=name, description=description or "新项目"),
        encoding="utf-8"
    )
    (const_dir / "tech-stack.md").write_text(
        TECHSTACK_TEMPLATE.format(name=name),
        encoding="utf-8"
    )

    _update_architecture_manifest(name, proj_type)

    return {
        "status": "created",
        "name": name,
        "path": str(project_dir),
        "files_created": [
            str(const_dir / "architecture.md"),
            str(const_dir / "decisions.md"),
            str(const_dir / "tech-stack.md"),
        ]
    }


def _update_architecture_manifest(name: str, proj_type: str) -> None:
    arch_path = config.PORTFOLIO_ROOT / ".context" / "constitution" / "architecture.md"
    if not arch_path.exists():
        return
    content = arch_path.read_text(encoding="utf-8")
    marker = "├── products/" if proj_type == "product" else "├── experiments/"
    new_line = f"│   ├── {name}/"
    if new_line not in content:
        content = content.replace(marker, f"{marker}\n{new_line}")
        arch_path.write_text(content, encoding="utf-8")
