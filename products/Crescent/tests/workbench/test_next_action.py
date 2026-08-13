from services.workbench.types import Profile
from services.workbench.gap_analyzer import GapReport, GapItem
from services.workbench.learning_path import LearningPathGenerator, Phase, Module
from services.workbench.next_action import NextActionGenerator, ActionItem


class TestNextActionGenerator:
    def test_generate_returns_actions(self):
        path = LearningPathGenerator().generate(
            GapReport(gaps=[GapItem("python", "expert", "beginner", "must", "")]),
            Profile(),
        )
        gen = NextActionGenerator()
        actions = gen.generate(path, path.phases[0].name)
        assert len(actions) >= 1
        for a in actions:
            assert a.title
            assert a.estimated_time
            assert a.resource_type in ("tutorial", "course", "paper", "project", "book")

    def test_empty_path_returns_default_action(self):
        gen = NextActionGenerator()
        actions = gen.generate(LearningPathGenerator().generate(
            GapReport(gaps=[]), Profile()), "Phase 1")
        assert len(actions) >= 1
