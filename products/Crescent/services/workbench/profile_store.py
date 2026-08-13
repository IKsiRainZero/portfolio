from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken
import base64

from services.workbench.types import Profile, Skill, ProfileMeta


class ProfileStore:
    def __init__(self, data_dir: Path, password: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "profile.enc"
        self._salt_file = self.data_dir / "profile.salt"
        self._password = password
        self._fernet = self._derive_key(password)

    def _derive_key(self, password: str) -> Fernet:
        if self._salt_file.exists():
            salt = self._salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            self._salt_file.write_bytes(salt)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    def verify_password(self, password: str) -> bool:
        try:
            if not self._salt_file.exists() or not self._file.exists():
                return False
            salt = self._salt_file.read_bytes()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480_000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            fernet = Fernet(key)
            encrypted = self._file.read_bytes()
            fernet.decrypt(encrypted)
            return True
        except (InvalidToken, Exception):
            return False

    def load(self) -> Profile:
        if not self._file.exists():
            return Profile()
        try:
            encrypted = self._file.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            return Profile.from_dict(json.loads(decrypted))
        except (InvalidToken, Exception):
            return Profile()

    def save(self, profile: Profile) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not profile.meta.created_at:
            profile.meta.created_at = now
        profile.meta.updated_at = now
        profile.meta.completeness = self.compute_completeness(profile)
        plain = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)
        self._file.write_bytes(self._fernet.encrypt(plain.encode()))

    def upsert_skills(self, new_skills: dict[str, Skill]) -> Profile:
        profile = self.load()
        for name, skill in new_skills.items():
            if name in profile.skills and skill.confidence < profile.skills[name].confidence:
                continue
            profile.skills[name] = skill
        self.save(profile)
        return profile

    def compute_completeness(self, profile: Profile) -> float:
        score = 0.0
        if profile.skills:
            score += 0.4
        if profile.experiences:
            score += 0.25
        if profile.preferences.industry:
            score += 0.15
        if profile.interests:
            score += 0.1
        if profile.education and profile.education.school:
            score += 0.1
        return min(score, 1.0)

    def export(self, password: str, output_path: Path | None = None) -> Path:
        profile = self.load()
        ts = datetime.now().strftime("%Y-%m-%d")
        out = output_path or self.data_dir / f"profile-export-{ts}.json"
        out.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out
