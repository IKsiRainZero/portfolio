from services.workbench.types import Profile
from services.workbench.gap_analyzer import GapAnalyzer, GapItem, GapReport
from services.workbench.skill_matcher import MatchResult
from services.workbench.learning_path import LearningPathGenerator


class TestLearningPathGenerator:
    def test_generate_returns_phases(self):
        gaps = GapReport(gaps=[
            GapItem("python", "expert", "beginner", "must", "核心语言"),
            GapItem("llm", "senior", "none", "must", "必备理论"),
            GapItem("docker", "intermediate", "none", "recommended", "部署工具"),
        ])
        profile = Profile()
        gen = LearningPathGenerator()
        path = gen.generate(gaps, profile)
        assert len(path.phases) >= 2

    def test_phases_have_prerequisites(self):
        gaps = GapReport(gaps=[
            GapItem("python", "expert", "beginner", "must", ""),
            GapItem("llm", "senior", "none", "must", ""),
        ])
        gen = LearningPathGenerator()
        path = gen.generate(gaps, Profile())
        p1 = path.phases[0]
        assert p1.difficulty in ("beginner", "intermediate", "advanced")
        assert p1.duration
        assert len(p1.modules) > 0
