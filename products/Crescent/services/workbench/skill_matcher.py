from __future__ import annotations
from dataclasses import dataclass, field

from services.workbench.types import Profile, Skill, SKILL_ALIASES, normalize_skill
from services.workbench.industry_scanner import (
    IndustryTrend, SkillRequirementSet, SkillRequirement, Source,
)



@dataclass
class MatchResult:
    direction: str
    score: float
    skill_overlap: list[str]
    skill_gap: list[str]
    transferability: float
    rationale: str
    sources: list[Source] = field(default_factory=list)


class SkillMatcher:
    def match(self, profile: Profile, trends: list[IndustryTrend]) -> list[MatchResult]:
        context = self._context_reading(profile, trends)
        user_skills = {normalize_skill(s.skill_name) for s in profile.skills.values()}
        results: list[MatchResult] = []

        for trend in trends:
            req_names = {normalize_skill(r.skill_name)
                         for r in trend.skill_requirements.skills}
            overlap = user_skills & req_names
            gap = req_names - user_skills
            similarity = self._compute_similarity(user_skills, req_names)
            transferability = self._compute_transferability(user_skills, req_names)

            # Preference/interest boost
            pref_boost = 0.0
            pref = profile.preferences.industry
            if pref and pref.lower() in trend.direction.lower():
                pref_boost += 20.0
            for interest in profile.interests:
                if interest.lower() in trend.direction.lower():
                    pref_boost += 10.0

            score = round((similarity * 60 + transferability * 40) + pref_boost, 1)

            results.append(MatchResult(
                direction=trend.direction,
                score=score,
                skill_overlap=sorted(overlap),
                skill_gap=sorted(gap),
                transferability=round(transferability, 2),
                rationale=self._generate_rationale(
                    trend.direction, overlap, gap, transferability, profile
                ),
                sources=trend.sources,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _context_reading(self, profile: Profile, trends: list[IndustryTrend]) -> str:
        skill_names = list(profile.skills.keys())
        exp_years = max((e.years for e in profile.experiences), default=0)
        trend_names = [t.direction for t in trends[:5]]
        lines = [
            f"该用户具备{', '.join(skill_names)}等技能，共约{exp_years}年经验。",
            f"偏好行业: {profile.preferences.industry or '未指定'}，",
            f"兴趣方向: {', '.join(profile.interests) if profile.interests else '未指定'}。",
            f"当前产业热门方向: {', '.join(trend_names)}。",
            f"根据用户Python/SQL基础，向AI/数据方向转型成本最低。",
        ]
        return "".join(lines)

    def _compute_similarity(self, user_skills: set[str],
                             required_skills: set[str]) -> float:
        if not required_skills:
            return 0.5
        intersection = user_skills & required_skills
        union = user_skills | required_skills
        jaccard = len(intersection) / len(union) if union else 0
        soft_bonus = 0.0
        for us in user_skills:
            for rs in required_skills:
                if us != rs and (us in rs or rs in us):
                    soft_bonus += 0.1
        return min(jaccard + soft_bonus, 1.0)

    def _compute_transferability(self, user_skills: set[str],
                                  required_skills: set[str]) -> float:
        high_transfer = {"python", "sql", "java", "go", "javascript"}
        ai_skills = {"llm", "ml", "pytorch", "tensorflow", "langchain", "rag"}
        user_high = user_skills & high_transfer
        req_ai = required_skills & ai_skills
        if user_high and req_ai:
            return 0.7 + min(len(user_high) * 0.1, 0.3)
        if user_high:
            return 0.5
        return 0.3

    def _generate_rationale(self, direction: str, overlap: set[str], gap: set[str],
                             transferability: float, profile: Profile) -> str:
        parts = []
        if overlap:
            parts.append(f"已有技能 {', '.join(overlap)} 直接匹配{direction}需求")
        if gap:
            parts.append(f"缺失 {', '.join(gap)}，需要学习")
        if transferability > 0.6:
            parts.append("技能可迁移度高")
        pref = profile.preferences.industry
        if pref and pref.lower() in direction.lower():
            parts.append(f"符合用户行业偏好({pref})")
        return "。".join(parts) + "。"
