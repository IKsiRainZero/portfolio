from services.workbench.types import (
    Skill, Experience, Preference, Education,
    ProfileMeta, Profile, WorkbenchEvent,
)


class TestSkill:
    def test_skill_to_dict_and_back(self):
        s = Skill(skill_name="Python", years=3, level="senior",
                   evidence="三年后端开发", confidence=0.9)
        d = s.to_dict()
        s2 = Skill.from_dict(d)
        assert s2.skill_name == "Python"
        assert s2.years == 3
        assert s2.level == "senior"
        assert s2.evidence == "三年后端开发"
        assert s2.confidence == 0.9

    def test_skill_defaults(self):
        s = Skill(skill_name="Go", years=0)
        assert s.level == "intermediate"
        assert s.confidence == 0.5


class TestProfile:
    def test_empty_profile_roundtrip(self):
        p = Profile()
        d = p.to_dict()
        p2 = Profile.from_dict(d)
        assert p2.skills == {}
        assert p2.experiences == []
        assert p2.interests == []
        assert p2.meta.completeness == 0.0

    def test_full_profile_roundtrip(self):
        p = Profile(
            skills={"python": Skill("python", 3, "senior", "做了三年", 0.9)},
            experiences=[Experience("后端", "某公司", 3, ["API设计"])],
            preferences=Preference(industry="AI", location="北京"),
            interests=["开源", "AI"],
            education=Education(school="某大学", degree="本科", major="CS"),
            meta=ProfileMeta(completeness=0.4),
        )
        d = p.to_dict()
        p2 = Profile.from_dict(d)
        assert p2.skills["python"].skill_name == "python"
        assert p2.experiences[0].role == "后端"
        assert p2.preferences.industry == "AI"
        assert p2.interests == ["开源", "AI"]
        assert p2.education.school == "某大学"
        assert p2.meta.completeness == 0.4


class TestWorkbenchEvent:
    def test_event_creation(self):
        e = WorkbenchEvent(
            event_type="profile.updated",
            panel_id="profile",
            payload={"skills": ["Python"]},
        )
        assert e.event_type == "profile.updated"
        assert e.panel_id == "profile"
        assert e.payload == {"skills": ["Python"]}
