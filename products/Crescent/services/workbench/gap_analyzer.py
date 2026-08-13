from __future__ import annotations
from dataclasses import dataclass, field

from services.workbench.types import Profile, Skill
from services.workbench.skill_matcher import MatchResult

_CORE_SKILLS = {"python", "java", "go", "javascript", "sql", "llm", "ml",
                 "kubernetes", "aws", "react"}
_SECONDARY_SKILLS = {"docker", "git", "linux", "rest", "graphql", "redis",
                      "postgresql", "mongodb", "kafka", "rabbitmq",
                      "langchain", "rag", "pytorch", "tensorflow", "mlflow"}
_TOOL_SKILLS = {"jupyter", "pandas", "numpy", "matplotlib", "seaborn",
                "postman", "swagger", "grafana", "prometheus", "terraform",
                "ansible", "jenkins", "github actions"}


@dataclass
class GapItem:
    skill_name: str
    required_level: str    # "beginner" | "intermediate" | "senior" | "expert"
    current_level: str
    priority: str          # "must" | "recommended" | "optional"
    rationale: str


@dataclass
class GapReport:
    gaps: list[GapItem] = field(default_factory=list)


class GapAnalyzer:
    def analyze(self, profile: Profile, direction: MatchResult) -> GapReport:
        gaps: list[GapItem] = []
        user_skills = {s.skill_name.lower(): s for s in profile.skills.values()}

        for skill_name in direction.skill_gap:
            nl = skill_name.lower()
            if nl in _CORE_SKILLS:
                priority = "must"
            elif nl in _SECONDARY_SKILLS:
                priority = "recommended"
            else:
                priority = "optional"

            existing = user_skills.get(nl)
            current_level = existing.level if existing else "none"
            required_level = self._estimate_required_level(nl, priority)

            gaps.append(GapItem(
                skill_name=skill_name,
                required_level=required_level,
                current_level=current_level,
                priority=priority,
                rationale=self._rationale(skill_name, priority),
            ))

        gaps.sort(key=lambda g: {"must": 0, "recommended": 1, "optional": 2}[g.priority])
        return GapReport(gaps=gaps)

    def _estimate_required_level(self, skill_name: str, priority: str) -> str:
        nl = skill_name.lower()
        if nl in _CORE_SKILLS:
            return "intermediate" if priority == "must" else "beginner"
        return "beginner"

    def _rationale(self, skill_name: str, priority: str) -> str:
        maps = {
            "must": f"{skill_name} 是目标方向的核心技能，不具备则无法入门",
            "recommended": f"{skill_name} 显著提升在该方向的竞争力",
            "optional": f"{skill_name} 是锦上添花的工具，非必需",
        }
        return maps[priority]
