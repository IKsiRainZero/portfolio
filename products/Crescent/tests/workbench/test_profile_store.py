import json
import tempfile
from pathlib import Path
from services.workbench.profile_store import ProfileStore
from services.workbench.types import Profile, Skill, Preference, ProfileMeta


class TestProfileStore:
    def _make_store(self, pw="t3st"):
        tmp = tempfile.mkdtemp()
        return ProfileStore(data_dir=Path(tmp), password=pw), tmp

    def test_save_and_load_roundtrip(self):
        store, _ = self._make_store()
        p = Profile(
            skills={"python": Skill("python", 3, "senior", "三年后端", 0.9)},
            preferences=Preference(industry="AI"),
        )
        store.save(p)
        loaded = store.load()
        assert loaded.skills["python"].skill_name == "python"
        assert loaded.skills["python"].years == 3
        assert loaded.preferences.industry == "AI"

    def test_new_profile_when_no_file(self):
        store, _ = self._make_store()
        p = store.load()
        assert p.skills == {}
        assert p.meta.completeness == 0.0

    def test_encrypted_file_is_not_plain_json(self):
        store, tmp = self._make_store()
        store.save(Profile(skills={"python-web": Skill("python-web", 1, "beginner", "", 0.5)}))
        enc_path = Path(tmp) / "profile.enc"
        raw = enc_path.read_bytes()
        assert b"python-web" not in raw

    def test_wrong_password_cannot_load(self):
        store_a, tmp = self._make_store("c0rrect")
        store_a.save(Profile(preferences=Preference(industry="AI")))
        wrong_pw = "wr0ng"
        store_b = ProfileStore(data_dir=Path(tmp), password=wrong_pw)
        p = store_b.load()
        assert p.skills == {}
        assert p.meta.completeness == 0.0

    def test_upsert_skills_merges(self):
        store, _ = self._make_store()
        store.save(Profile(skills={"python": Skill("python", 3, "senior", "old", 0.7)}))
        store.upsert_skills({"python": Skill("python", 4, "expert", "new", 0.95),
                              "sql": Skill("sql", 2, "intermediate", "mentioned", 0.8)})
        loaded = store.load()
        assert loaded.skills["python"].years == 4
        assert loaded.skills["python"].level == "expert"
        assert "sql" in loaded.skills

    def test_compute_completeness(self):
        store, _ = self._make_store()
        p = Profile(skills={"a": Skill("a", 1, "beginner", "", 0.5)},
                     preferences=Preference(industry="AI"))
        c = store.compute_completeness(p)
        assert 0.0 < c < 1.0

    def test_compute_completeness_full(self):
        store, _ = self._make_store()
        p = Profile(
            skills={"a": Skill("a", 1, "beginner", "", 0.5)},
            preferences=Preference(industry="AI", location="北京"),
            interests=["开源"],
            experiences=[{"role": "后端", "company": "X", "years": 3, "highlights": []}],
        )
        c = store.compute_completeness(p)
        assert c >= 0.5

    def test_export_writes_plain_json(self):
        store, tmp = self._make_store()
        store.save(Profile(preferences=Preference(industry="AI")))
        out = store.export("test123")
        raw = out.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["preferences"]["industry"] == "AI"

    def test_verify_password_correct(self):
        store, _ = self._make_store("hunter2")
        store.save(Profile())
        assert store.verify_password("hunter2") is True

    def test_verify_password_wrong(self):
        store, _ = self._make_store("hunter2")
        store.save(Profile())
        assert store.verify_password("wrong") is False
