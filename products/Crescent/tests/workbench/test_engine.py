from services.workbench.engine import PanelStateManager, WorkbenchEngine
from services.workbench.types import WorkbenchEvent
from services.workbench.profile_store import ProfileStore
from services.workbench.industry_scanner import IndustryScanner
from services.workbench.skill_matcher import SkillMatcher
from services.workbench.gap_analyzer import GapAnalyzer
from services.workbench.learning_path import LearningPathGenerator
from services.workbench.next_action import NextActionGenerator
import tempfile
from pathlib import Path


class TestPanelStateManager:
    def test_initial_state_all_empty(self):
        psm = PanelStateManager()
        for pid in ["profile", "direction", "gap", "source", "path", "action"]:
            assert psm.get_state(pid) == "EMPTY"

    def test_set_state_returns_event(self):
        psm = PanelStateManager()
        events = psm.set_state("profile", "PARTIAL", {"skills": ["Python"]})
        assert len(events) >= 1
        e = events[0]
        assert e.panel_id == "profile"
        assert e.payload["skills"] == ["Python"]

    def test_confirm_profile_triggers_direction_event(self):
        psm = PanelStateManager()
        psm.set_state("profile", "READY_FOR_REVIEW", {})
        events = psm.confirm("profile")
        assert psm.get_state("profile") == "CONFIRMED"
        event_types = [e.event_type for e in events]
        assert "profile.confirmed" in event_types

    def test_revoke_direction_resets_downstream(self):
        psm = PanelStateManager()
        psm.set_state("profile", "CONFIRMED", {})
        psm.set_state("direction", "CONFIRMED", {})
        psm.set_state("gap", "READY_FOR_REVIEW", {})
        psm.set_state("path", "PARTIAL", {})
        psm.set_state("action", "PARTIAL", {})

        events = psm.revoke("direction")
        assert psm.get_state("direction") == "EMPTY"
        assert psm.get_state("gap") == "EMPTY"
        assert psm.get_state("path") == "EMPTY"
        assert psm.get_state("action") == "EMPTY"

    def test_dependencies_declared(self):
        deps = PanelStateManager.PANEL_DEPENDENCIES
        assert deps["profile"] == []
        assert "profile" in deps["direction"]
        assert "direction" in deps["gap"]
        assert "direction" in deps["path"]
        assert "path" in deps["action"]


class TestWorkbenchEngine:
    def _make_engine(self):
        tmp = Path(tempfile.mkdtemp())
        _pw = "t3st"
        store = ProfileStore(data_dir=tmp, password=_pw)
        return WorkbenchEngine(
            profile_store=store,
            scanner=IndustryScanner(),
            matcher=SkillMatcher(),
            analyzer=GapAnalyzer(),
            path_gen=LearningPathGenerator(),
            action_gen=NextActionGenerator(),
        )

    def test_handle_input_returns_events(self):
        engine = self._make_engine()
        events = engine.handle_input("user1", "我做了三年Python后端开发")
        assert len(events) > 0
        assert any(e.panel_id == "profile" for e in events)

    def test_handle_input_extracts_skills(self):
        engine = self._make_engine()
        engine.handle_input("user1", "我做了三年Python后端，熟悉Django和PostgreSQL")
        profile = engine._profile_store.load()
        assert "python" in profile.skills or len(profile.skills) > 0

    def test_confirm_panel_profile(self):
        engine = self._make_engine()
        engine.handle_input("user1", "我是Python后端，三年经验，用过Django、Flask")
        events = engine.confirm_panel("user1", "profile")
        assert any(e.event_type == "profile.confirmed" for e in events)
