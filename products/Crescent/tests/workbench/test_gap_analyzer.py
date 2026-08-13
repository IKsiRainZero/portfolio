from services.workbench.types import Profile, Skill
from services.workbench.skill_matcher import MatchResult
from services.workbench.gap_analyzer import GapAnalyzer, GapReport, GapItem


class TestGapAnalyzer:
    def test_analyze_classifies_must_recommended_optional(self):
        profile = Profile(skills={"python": Skill("python", 3, "senior", "evidence", 0.9)})
        direction = MatchResult(
            direction="AI Agent 开发", score=75,
            skill_overlap=["python"], skill_gap=["llm", "langchain", "docker"],
            transferability=0.8, rationale="...",
        )
        analyzer = GapAnalyzer()
        report = analyzer.analyze(profile, direction)

        priorities = {g.skill_name: g.priority for g in report.gaps}
        assert priorities["llm"] == "must"
        assert priorities["langchain"] in ("must", "recommended")
        assert priorities["docker"] in ("recommended", "optional")

    def test_gaps_sorted_by_priority(self):
        profile = Profile(skills={})
        direction = MatchResult(
            direction="MLOps", score=30,
            skill_overlap=[], skill_gap=["python", "k8s", "mlflow"],
            transferability=0.3, rationale="...",
        )
        analyzer = GapAnalyzer()
        report = analyzer.analyze(profile, direction)
        musts = [g for g in report.gaps if g.priority == "must"]
        recs  = [g for g in report.gaps if g.priority == "recommended"]
        opts  = [g for g in report.gaps if g.priority == "optional"]
        assert len(musts) > 0
        idx_must = report.gaps.index(musts[0])
        idx_rec = report.gaps.index(recs[0]) if recs else 999
        idx_opt = report.gaps.index(opts[0]) if opts else 999
        assert idx_must < idx_rec
        assert idx_rec < idx_opt
