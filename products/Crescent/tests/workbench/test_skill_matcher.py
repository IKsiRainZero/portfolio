from services.workbench.types import Profile, Skill, Preference
from services.workbench.industry_scanner import (
    IndustryTrend, SkillRequirementSet, SkillRequirement, Source,
)
from services.workbench.skill_matcher import SkillMatcher, MatchResult


def _make_profile(skills: dict | None = None) -> Profile:
    return Profile(
        skills=skills or {
            "python": Skill("python", 3, "senior", "三年后端", 0.9),
            "sql": Skill("sql", 3, "intermediate", "日常使用", 0.8),
        },
        preferences=Preference(industry="AI"),
        interests=["开源", "AI"],
    )


def _make_trends() -> list[IndustryTrend]:
    return [
        IndustryTrend(
            direction="AI Agent 开发",
            heat_score=0.9,
            source_count=5,
            skill_requirements=SkillRequirementSet(skills=[
                SkillRequirement("python", "must", 8),
                SkillRequirement("llm", "must", 6),
                SkillRequirement("langchain", "recommended", 4),
            ]),
            trend_timeline="上升期",
            sources=[Source("serpapi", "AI Jobs", "http://x.com", "AI", "2026-01-01")],
        ),
        IndustryTrend(
            direction="数据工程",
            heat_score=0.6,
            source_count=3,
            skill_requirements=SkillRequirementSet(skills=[
                SkillRequirement("sql", "must", 8),
                SkillRequirement("python", "recommended", 5),
            ]),
            trend_timeline="成熟期",
            sources=[Source("hn", "Data Eng", "http://y.com", "DE", "2026-01-01")],
        ),
    ]


class TestSkillMatcher:
    def test_match_returns_results(self):
        matcher = SkillMatcher()
        results = matcher.match(_make_profile(), _make_trends())
        assert len(results) >= 1
        for r in results:
            assert 0 <= r.score <= 100
            assert r.direction
            assert r.rationale

    def test_match_scores_python_ai_higher(self):
        matcher = SkillMatcher()
        results = matcher.match(_make_profile(), _make_trends())
        scores = {r.direction: r.score for r in results}
        assert scores.get("AI Agent 开发", 0) > scores.get("数据工程", 0)

    def test_compute_similarity_identical(self):
        matcher = SkillMatcher()
        s = matcher._compute_similarity({"python", "sql"}, {"python", "sql"})
        assert s > 0.9

    def test_compute_similarity_no_overlap(self):
        matcher = SkillMatcher()
        s = matcher._compute_similarity({"python"}, {"java", "go"})
        assert s < 0.2

    def test_context_reading_not_empty(self):
        matcher = SkillMatcher()
        reading = matcher._context_reading(_make_profile(), _make_trends())
        assert len(reading) > 20
        assert "python" in reading.lower()
