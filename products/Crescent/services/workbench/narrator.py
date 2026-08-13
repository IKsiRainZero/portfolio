"""
LLM narrator for the workbench pipeline.
Replaces regex extraction + template-based generation with DeepSeek-powered
natural language understanding and content generation.
"""
from __future__ import annotations
import json
import re
import sys
from dataclasses import dataclass, field

from services.deepseek_client import chat, load_prompt
from services.workbench.types import (
    Profile, Skill, Experience, Preference, Education,
    SKILL_ALIASES, normalize_skill,
)


@dataclass
class ParsedInput:
    skills: dict[str, Skill] = field(default_factory=dict)
    experiences: list[Experience] = field(default_factory=list)
    preferences: Preference = field(default_factory=Preference)
    interests: list[str] = field(default_factory=list)
    education: Education | None = None
    intent: str = "other"          # "profile_update" | "query" | "confirm" | "other"
    intent_summary: str = ""
    raw_response: str = ""


def _extract_json(text: str) -> dict | None:
    """Extract JSON object from LLM response, handling markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... } pair
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


class WorkbenchNarrator:
    def __init__(self):
        self._prompt_cache: dict[str, str] = {}

    def _load(self, name: str) -> str:
        if name not in self._prompt_cache:
            self._prompt_cache[name] = load_prompt(name)
        return self._prompt_cache[name]

    # ── Step 1: Query rewriting / input parsing ──

    def parse_user_input(self, text: str, existing_profile: Profile | None = None) -> ParsedInput:
        """Parse natural language user input into structured profile data + intent.

        This replaces the regex-based _extract_skills_from_text() and
        keyword-based _is_profile_input() with LLM-powered NLU.
        """
        system = self._load("workbench_parse_input")

        context = ""
        if existing_profile and (existing_profile.skills or existing_profile.experiences):
            context = f"\n用户当前已记录的档案：\n{json.dumps(existing_profile.to_dict(), ensure_ascii=False, indent=2)}"

        messages = [{"role": "user", "content": f"用户输入：{text}{context}"}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.3, max_tokens=1200, timeout=25)
        except Exception as e:
            print(f"[narrator] parse_user_input LLM call failed: {e}", file=sys.stderr)
            return ParsedInput(intent="other", raw_response=str(e))

        data = _extract_json(reply)
        if not data:
            print(f"[narrator] parse_user_input JSON parse failed, raw: {reply[:200]}", file=sys.stderr)
            return ParsedInput(intent="other", raw_response=reply)

        result = ParsedInput(raw_response=reply)

        # Parse skills
        for s in data.get("skills", []):
            name = normalize_skill(s.get("name", ""))
            if not name:
                continue
            result.skills[name] = Skill(
                skill_name=name,
                years=float(s.get("years", 0.5)),
                level=s.get("level", "intermediate"),
                evidence=s.get("evidence", ""),
                confidence=0.75,  # LLM extraction confidence
            )

        # Parse experiences
        for e in data.get("experiences", []):
            result.experiences.append(Experience(
                role=e.get("role", ""),
                company=e.get("company"),
                years=float(e.get("years", 0)),
                highlights=e.get("highlights", []),
            ))

        # Parse preferences
        pref = data.get("preferences", {}) or {}
        result.preferences = Preference(
            industry=pref.get("industry"),
            location=pref.get("location"),
            work_style=pref.get("work_style"),
        )

        result.interests = data.get("interests", []) or []

        # Parse education
        edu = data.get("education")
        if edu and any(edu.values()):
            result.education = Education(
                school=edu.get("school"),
                degree=edu.get("degree"),
                major=edu.get("major"),
            )

        result.intent = data.get("intent", "other")
        result.intent_summary = data.get("intent_summary", "")
        return result

    # ── Step 2: Profile narration ──

    def narrate_profile(self, profile: Profile) -> dict:
        """Generate a natural language summary of the user's profile."""
        system = self._load("workbench_narrate_profile")
        profile_json = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)

        messages = [{"role": "user", "content": f"用户画像数据：\n{profile_json}"}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.7, max_tokens=800, timeout=25)
        except Exception as e:
            print(f"[narrator] narrate_profile LLM call failed: {e}", file=sys.stderr)
            return _fallback_profile_narrative(profile)

        data = _extract_json(reply)
        if not data:
            return _fallback_profile_narrative(profile)

        return {
            "summary": data.get("summary", ""),
            "experience": data.get("experience", ""),
            "skills": data.get("skills", []),
            "completeness": profile.meta.completeness,
            "skill_names": list(profile.skills.keys()),
            "count": len(profile.skills),
        }

    # ── Step 3: Direction narration ──

    def narrate_direction(self, matches: list, profile: Profile) -> dict:
        """Generate natural language direction match narratives."""
        system = self._load("workbench_narrate_direction")

        match_data = [
            {
                "direction": m.direction,
                "score": m.score,
                "overlap": m.skill_overlap,
                "gap": m.skill_gap,
                "transferability": m.transferability,
            }
            for m in matches[:3]
        ]
        profile_json = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)
        user_msg = f"用户画像：\n{profile_json}\n\n匹配结果：\n{json.dumps(match_data, ensure_ascii=False, indent=2)}"

        messages = [{"role": "user", "content": user_msg}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.7, max_tokens=1200, timeout=25)
        except Exception as e:
            print(f"[narrator] narrate_direction LLM call failed: {e}", file=sys.stderr)
            return _fallback_direction_narrative(matches)

        data = _extract_json(reply)
        if not data:
            return _fallback_direction_narrative(matches)

        return {
            "directions": data.get("directions", []),
            "top_match": matches[0].direction if matches else "",
            "top_score": matches[0].score if matches else 0,
        }

    # ── Step 4: Gap narration ──

    def narrate_gap(self, gaps: list, profile: Profile, direction_name: str) -> dict:
        """Generate natural language gap analysis."""
        system = self._load("workbench_narrate_gap")

        gap_data = [
            {"skill": g.skill_name, "required": g.required_level,
             "current": g.current_level, "priority": g.priority}
            for g in gaps
        ]
        user_msg = (
            f"用户画像：\n{json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)}\n\n"
            f"目标方向：{direction_name}\n\n"
            f"技能差距：\n{json.dumps(gap_data, ensure_ascii=False, indent=2)}"
        )

        messages = [{"role": "user", "content": user_msg}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.7, max_tokens=1200, timeout=25)
        except Exception as e:
            print(f"[narrator] narrate_gap LLM call failed: {e}", file=sys.stderr)
            return _fallback_gap_narrative(gaps)

        data = _extract_json(reply)
        if not data:
            return _fallback_gap_narrative(gaps)

        must_learn = data.get("mustLearn", [])
        recommend = data.get("recommend", [])
        all_gaps = must_learn + recommend

        return {
            "gaps": all_gaps,
            "mustLearn": must_learn,
            "recommend": recommend,
            "must_count": len(must_learn),
            "rec_count": len(recommend),
            "gap_count": len(all_gaps),
        }

    # ── Step 5: Path narration ──

    def narrate_path(self, gaps: list, profile: Profile, direction_name: str) -> dict:
        """Generate a natural language learning path."""
        system = self._load("workbench_narrate_path")

        gap_data = [
            {"skill": g.skill_name, "priority": g.priority,
             "current": g.current_level, "required": g.required_level}
            for g in gaps
        ]
        user_msg = (
            f"用户画像：\n{json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)}\n\n"
            f"目标方向：{direction_name}\n\n"
            f"技能差距：\n{json.dumps(gap_data, ensure_ascii=False, indent=2)}"
        )

        messages = [{"role": "user", "content": user_msg}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.7, max_tokens=1200, timeout=25)
        except Exception as e:
            print(f"[narrator] narrate_path LLM call failed: {e}", file=sys.stderr)
            return _fallback_path_narrative(gaps)

        data = _extract_json(reply)
        if not data:
            return _fallback_path_narrative(gaps)

        phases = data.get("phases", [])
        return {
            "phases": phases,
            "phase_count": len(phases),
        }

    # ── Step 6: Action narration ──

    def narrate_action(self, path_phases: list[dict], gaps: list) -> dict:
        """Generate natural language next-action items."""
        system = self._load("workbench_narrate_action")

        first_phase = path_phases[0] if path_phases else {"title": "基础巩固", "modules": []}
        gap_data = [
            {"skill": g.skill_name, "priority": g.priority} for g in gaps[:5]
        ]

        user_msg = (
            f"学习路径第一阶段：\n{json.dumps(first_phase, ensure_ascii=False, indent=2)}\n\n"
            f"技能差距：\n{json.dumps(gap_data, ensure_ascii=False, indent=2)}"
        )

        messages = [{"role": "user", "content": user_msg}]

        try:
            reply, _ = chat(messages, system_prompt=system, temperature=0.7, max_tokens=800, timeout=25)
        except Exception as e:
            print(f"[narrator] narrate_action LLM call failed: {e}", file=sys.stderr)
            return _fallback_action_narrative()

        data = _extract_json(reply)
        if not data:
            return _fallback_action_narrative()

        return {
            "actions": data.get("actions", []),
            "action_count": len(data.get("actions", [])),
        }


# ── Fallback generators (used when LLM is unavailable) ──

def _fallback_profile_narrative(profile: Profile) -> dict:
    skill_names = list(profile.skills.keys())
    skills = []
    for name, s in profile.skills.items():
        if name in ("python", "javascript", "go", "java", "rust", "c++", "sql"):
            cat = "language"
        elif name in ("react", "fastapi", "django", "flask", "pytorch", "tensorflow"):
            cat = "framework"
        elif name in ("docker", "kubernetes", "aws", "git", "linux"):
            cat = "tool"
        else:
            cat = "soft"
        skills.append({"name": s.skill_name, "category": cat})

    exp_years = max((e.years for e in profile.experiences), default=0)
    summary_parts = []
    if skill_names:
        summary_parts.append(f"具备{', '.join(skill_names[:5])}等技能")
    if exp_years:
        summary_parts.append(f"约{exp_years:.0f}年开发经验")
    summary = "。".join(summary_parts) + "。" if summary_parts else "请描述你的技能和经历，系统将生成能力画像。"

    return {
        "summary": summary,
        "experience": f"{exp_years:.0f}年" if exp_years else "—",
        "skills": skills,
        "completeness": profile.meta.completeness,
        "skill_names": skill_names,
        "count": len(skill_names),
    }


def _fallback_direction_narrative(matches: list) -> dict:
    directions = []
    for m in matches[:3]:
        directions.append({
            "name": m.direction,
            "matchScore": m.score,
            "reason": m.rationale,
            "overlaps": m.skill_overlap,
            "gaps": m.skill_gap,
            "outlook": "stable",
        })
    return {
        "directions": directions,
        "top_match": matches[0].direction if matches else "",
        "top_score": matches[0].score if matches else 0,
    }


def _fallback_gap_narrative(gaps: list) -> dict:
    must = []
    rec = []
    for g in gaps:
        item = {
            "skill": g.skill_name,
            "priority": "high" if g.priority == "must" else ("medium" if g.priority == "recommended" else "low"),
            "difficulty": "moderate",
            "estHours": 40,
            "reason": g.rationale,
        }
        if g.priority == "must":
            must.append(item)
        else:
            rec.append(item)
    all_gaps = must + rec
    return {
        "gaps": all_gaps,
        "mustLearn": must,
        "recommend": rec,
        "must_count": len(must),
        "rec_count": len(rec),
        "gap_count": len(all_gaps),
    }


def _fallback_path_narrative(gaps: list) -> dict:
    must_skills = [g.skill_name for g in gaps if getattr(g, 'priority', '') == 'must']
    rec_skills = [g.skill_name for g in gaps if getattr(g, 'priority', '') == 'recommended']
    phases = []
    if must_skills:
        phases.append({
            "title": "第一阶段：核心基础",
            "duration": "约 3-5 周",
            "difficulty": "中等",
            "modules": must_skills[:5],
            "outcome": f"掌握 {', '.join(must_skills[:3])} 等核心技能的基础使用",
        })
    if rec_skills:
        phases.append({
            "title": "第二阶段：技能深化",
            "duration": "约 4-6 周",
            "difficulty": "中高",
            "modules": rec_skills[:4],
            "outcome": f"能独立运用 {', '.join(rec_skills[:2])} 解决实际问题",
        })
    if not phases:
        phases.append({
            "title": "第一阶段：基础巩固",
            "duration": "约 2-4 周",
            "difficulty": "中等",
            "modules": ["基础知识回顾", "实践项目"],
            "outcome": "巩固现有技能基础，为后续学习做准备",
        })
    return {"phases": phases, "phase_count": len(phases)}


def _fallback_action_narrative() -> dict:
    actions = [
        {"text": "明确学习目标：写下你想达成的具体职业方向", "estTime": "30分钟", "priority": "high", "done": False},
        {"text": "收集学习资源：整理3-5个高质量教程或课程", "estTime": "1小时", "priority": "high", "done": False},
        {"text": "制定学习计划：按周分解学习任务", "estTime": "30分钟", "priority": "medium", "done": False},
    ]
    return {"actions": actions, "action_count": len(actions)}
