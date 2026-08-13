from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime, timezone


@dataclass
class Skill:
    skill_name: str
    years: float
    level: str = "intermediate"   # "beginner" | "intermediate" | "senior" | "expert"
    evidence: str = ""            # quote from user's natural language
    confidence: float = 0.5       # 0.0–1.0, LLM extraction confidence

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "years": self.years,
            "level": self.level,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Skill:
        return cls(
            skill_name=d["skill_name"],
            years=d["years"],
            level=d.get("level", "intermediate"),
            evidence=d.get("evidence", ""),
            confidence=d.get("confidence", 0.5),
        )


@dataclass
class Experience:
    role: str
    company: str | None
    years: float
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "company": self.company,
            "years": self.years,
            "highlights": self.highlights,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Experience:
        return cls(
            role=d["role"],
            company=d.get("company"),
            years=d["years"],
            highlights=d.get("highlights", []),
        )


@dataclass
class Preference:
    industry: str | None = None
    location: str | None = None
    salary_range: str | None = None
    work_style: str | None = None

    def to_dict(self) -> dict:
        return {
            "industry": self.industry,
            "location": self.location,
            "salary_range": self.salary_range,
            "work_style": self.work_style,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Preference:
        return cls(
            industry=d.get("industry"),
            location=d.get("location"),
            salary_range=d.get("salary_range"),
            work_style=d.get("work_style"),
        )


@dataclass
class Education:
    school: str | None = None
    degree: str | None = None
    major: str | None = None

    def to_dict(self) -> dict:
        return {"school": self.school, "degree": self.degree, "major": self.major}

    @classmethod
    def from_dict(cls, d: dict) -> Education:
        return cls(
            school=d.get("school"),
            degree=d.get("degree"),
            major=d.get("major"),
        )


@dataclass
class ProfileMeta:
    created_at: str = ""
    updated_at: str = ""
    completeness: float = 0.0
    password_salt: bytes | None = None

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completeness": self.completeness,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProfileMeta:
        return cls(
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            completeness=d.get("completeness", 0.0),
        )


@dataclass
class Profile:
    skills: dict[str, Skill] = field(default_factory=dict)
    experiences: list[Experience] = field(default_factory=list)
    preferences: Preference = field(default_factory=Preference)
    interests: list[str] = field(default_factory=list)
    education: Education | None = None
    meta: ProfileMeta = field(default_factory=ProfileMeta)

    def to_dict(self) -> dict:
        return {
            "skills": {k: v.to_dict() for k, v in self.skills.items()},
            "experiences": [e.to_dict() for e in self.experiences],
            "preferences": self.preferences.to_dict(),
            "interests": self.interests,
            "education": self.education.to_dict() if self.education else None,
            "meta": self.meta.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Profile:
        return cls(
            skills={k: Skill.from_dict(v) for k, v in d.get("skills", {}).items()},
            experiences=[Experience.from_dict(e) for e in d.get("experiences", [])],
            preferences=Preference.from_dict(d.get("preferences", {})),
            interests=d.get("interests", []),
            education=Education.from_dict(ed) if (ed := d.get("education")) else None,
            meta=ProfileMeta.from_dict(d.get("meta", {})),
        )


# Shared skill alias map — canonical name → list of aliases (lowercase).
# engine.py uses this to canonicalize extracted skills.
# skill_matcher.py uses this to normalize skill names during matching.
SKILL_ALIASES: dict[str, list[str]] = {
    "python":     ["python", "python3", "py", "django", "flask", "fastapi"],
    "sql":        ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "java":       ["java", "spring", "jvm"],
    "go":         ["go", "golang"],
    "javascript": ["javascript", "js", "typescript", "ts", "node", "nodejs"],
    "react":      ["react", "vue", "angular", "前端框架"],
    "rust":       ["rust", "cargo"],
    "c++":        ["c++", "cpp", "cplusplus"],
    "llm":        ["llm", "大模型", "gpt", "transformer", "openai"],
    "ml":         ["ml", "machine learning", "机器学习", "deep learning", "深度学习"],
    "cloud":      ["aws", "azure", "gcp", "cloud", "云"],
    "k8s":        ["kubernetes", "k8s", "docker", "container", "容器"],
    "ci/cd":      ["ci/cd", "ci", "cd", "jenkins", "github actions", "gitlab ci"],
}


def normalize_skill(name: str) -> str:
    """Map a raw skill name to its canonical form using SKILL_ALIASES."""
    n = name.lower().strip()
    for canonical, aliases in SKILL_ALIASES.items():
        if n in aliases:
            return canonical
    return n


@dataclass
class WorkbenchEvent:
    event_type: str     # "profile.updated" | "direction.matched" |
                        # "direction.confirmed" | "gap.analyzed" |
                        # "source.indexed" | "path.generated" |
                        # "path.confirmed" | "action.generated" |
                        # "panel.stale" | "profile.confirmed" |
                        # "gap.confirmed" | "action.confirmed" |
                        # "panel.revoked"
    panel_id: str       # "profile" | "direction" | "gap" | "source" | "path" | "action"
    payload: dict = field(default_factory=dict)
    timestamp: str = ""


PanelState = Literal["EMPTY", "PARTIAL", "READY_FOR_REVIEW", "CONFIRMED", "STALE"]
