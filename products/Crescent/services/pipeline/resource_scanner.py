from __future__ import annotations
import os
import json
import re
from pathlib import Path
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput
from services.deepseek_client import chat

L1_EXTENSIONS = {
    ".py", ".md", ".txt", ".pdf", ".docx",
    ".html", ".js", ".css", ".json", ".yaml",
    ".yml", ".toml",
}

SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git", "dist", "build"}


def _scan_l1(root: str) -> dict:
    """L1 surface scan: file types, counts, and metadata.

    Pure rules-based walk -- no LLM calls.
    Skips virtual environments and build/cache directories.
    """
    files = []
    root_path = Path(root).resolve()

    for dirpath_str, dirnames, filenames in os.walk(root_path):
        dirpath = Path(dirpath_str)

        # Skip excluded directories by pruning os.walk in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
        ]

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext not in L1_EXTENSIONS:
                continue

            full_path = dirpath / fname
            try:
                stat = full_path.stat()
                files.append({
                    "path": str(full_path),
                    "name": fname,
                    "ext": ext,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": stat.st_mtime,
                })
            except OSError:
                continue

    files.sort(key=lambda f: f["path"])

    return {
        "file_count": len(files),
        "files": files,
    }


def _scan_l2(file_summaries: list[dict]) -> dict:
    """L2 semantic scan: LLM extracts skills/projects/knowledge from file list.

    On LLM failure returns empty lists instead of crashing.
    """
    if not file_summaries:
        return {"skills": [], "projects": [], "knowledge_areas": [], "assets": [], "relations": []}

    summaries_text = "\n".join(
        f"- {f['path']}: {f.get('summary', '')[:200]}"
        for f in file_summaries[:50]
    )

    prompt = f"""Analyze the following local files and project structure to extract:

1. Skill tags (programming languages, frameworks, tools)
2. Projects (name + status: active/archived)
3. Knowledge areas covered
4. Available data assets
5. Relationships (between projects, between skills)

File list:
{summaries_text}

Output JSON:
{{"skills": ["skill1", ...], "projects": [{{"name": "...", "status": "active/archived"}}], "knowledge_areas": ["area1"], "assets": [{{"type": "...", "description": "..."}}], "relations": [{{"from": "...", "type": "...", "to": "..."}}]}}"""

    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a personal knowledge asset management assistant. Output JSON only.",
            temperature=0.2,
            max_tokens=1000,
            timeout=30,
        )

        text = reply.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        return json.loads(text)

    except Exception:
        return {"skills": [], "projects": [], "knowledge_areas": [], "assets": [], "relations": []}


class ResourceScannerStep:
    """S2: Scan local files to build a user asset snapshot.

    L1: rules-based directory walk counting file types and metadata.
    L2: LLM-driven semantic extraction of skills, projects, knowledge areas.
    """

    def __init__(self, name: str = "S2"):
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        return not input.config.get("scan_paths")

    def run(self, input: StepInput) -> StepOutput:
        scan_paths = input.config.get("scan_paths", [])
        if not scan_paths:
            return StepOutput(
                step_name=self.name,
                status="skipped",
                data={"reason": "No scan_paths configured"},
                confidence=1.0,
            )

        l1_results: dict[str, dict] = {}
        all_files: list[dict] = []

        for path in scan_paths:
            resolved = os.path.abspath(path)
            if os.path.isdir(resolved):
                l1 = _scan_l1(resolved)
                l1_results[path] = l1
                all_files.extend(l1["files"])
            elif os.path.isfile(resolved):
                entry = {
                    "path": resolved,
                    "name": Path(resolved).name,
                    "ext": Path(resolved).suffix.lower(),
                    "size_kb": round(os.path.getsize(resolved) / 1024, 1),
                    "modified": os.path.getmtime(resolved),
                }
                all_files.append(entry)

        if not all_files:
            return StepOutput(
                step_name=self.name,
                status="skipped",
                data={"reason": "No files found to scan"},
                confidence=1.0,
            )

        # L2: semantic scan with LLM (cap at 50 files)
        l2 = _scan_l2(all_files[:50])

        return StepOutput(
            step_name=self.name,
            status="ok",
            data={
                "l1_summary": {
                    path: {"file_count": v["file_count"]}
                    for path, v in l1_results.items()
                },
                **l2,
            },
            confidence=0.75,
        )
