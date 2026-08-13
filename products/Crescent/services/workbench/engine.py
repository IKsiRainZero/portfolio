from __future__ import annotations
from datetime import datetime, timezone
import json
import sys

from services.workbench.types import (
    Profile, Skill, Experience, Preference,
    WorkbenchEvent, PanelState,
    SKILL_ALIASES, normalize_skill,
)
from services.workbench.profile_store import ProfileStore
from services.workbench.industry_scanner import IndustryScanner, IndustryTrend
from services.workbench.skill_matcher import SkillMatcher, MatchResult
from services.workbench.gap_analyzer import GapAnalyzer, GapReport
from services.workbench.learning_path import LearningPathGenerator, LearningPath
from services.workbench.next_action import NextActionGenerator, ActionItem
from services.workbench.narrator import WorkbenchNarrator, ParsedInput


class PanelStateManager:
    PANEL_DEPENDENCIES: dict[str, list[str]] = {
        "profile":   [],
        "direction": ["profile"],
        "gap":       ["profile", "direction"],
        "source":    ["direction"],
        "path":      ["direction", "gap"],
        "action":    ["path"],
    }

    _DOWNSTREAM: dict[str, list[str]] = {}

    def __init__(self):
        self._states: dict[str, PanelState] = {
            pid: "EMPTY" for pid in self.PANEL_DEPENDENCIES
        }
        self._payloads: dict[str, dict] = {
            pid: {} for pid in self.PANEL_DEPENDENCIES
        }
        if not PanelStateManager._DOWNSTREAM:
            graph: dict[str, list[str]] = {
                pid: [] for pid in self.PANEL_DEPENDENCIES
            }
            for pid, deps in self.PANEL_DEPENDENCIES.items():
                for dep in deps:
                    graph[dep].append(pid)

            for pid in self.PANEL_DEPENDENCIES:
                visited: set[str] = set()
                queue: list[str] = list(graph[pid])
                while queue:
                    cur = queue.pop(0)
                    if cur in visited:
                        continue
                    visited.add(cur)
                    for downstream in graph.get(cur, []):
                        if downstream not in visited:
                            queue.append(downstream)
                PanelStateManager._DOWNSTREAM[pid] = list(visited)

    def get_state(self, panel_id: str) -> PanelState:
        return self._states.get(panel_id, "EMPTY")

    def get_payload(self, panel_id: str) -> dict:
        return self._payloads.get(panel_id, {})

    def set_state(self, panel_id: str, state: PanelState,
                  payload: dict | None = None) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        old_state = self._states.get(panel_id, "EMPTY")
        self._states[panel_id] = state
        if payload:
            self._payloads[panel_id] = payload

        ts = datetime.now(timezone.utc).isoformat()
        events.append(WorkbenchEvent(
            event_type=f"{panel_id}.updated",
            panel_id=panel_id,
            payload={"from": old_state, "to": state, **(payload or {})},
            timestamp=ts,
        ))

        if state == "CONFIRMED":
            events.append(WorkbenchEvent(
                event_type=f"{panel_id}.confirmed",
                panel_id=panel_id,
                payload={},
                timestamp=ts,
            ))

        return events

    def confirm(self, panel_id: str) -> list[WorkbenchEvent]:
        return self.set_state(panel_id, "CONFIRMED")

    def revoke(self, panel_id: str) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        ts = datetime.now(timezone.utc).isoformat()
        downstream = PanelStateManager._DOWNSTREAM.get(panel_id, [])
        for dpid in [panel_id] + downstream:
            self._states[dpid] = "EMPTY"
            self._payloads[dpid] = {}
            events.append(WorkbenchEvent(
                event_type=f"{dpid}.revoked",
                panel_id=dpid,
                payload={"reason": "upstream revoked"},
                timestamp=ts,
            ))
        return events

    def upstream_confirmed(self, panel_id: str) -> bool:
        for dep in self.PANEL_DEPENDENCIES.get(panel_id, []):
            if self._states.get(dep) != "CONFIRMED":
                return False
        return True


class WorkbenchEngine:
    def __init__(self, profile_store: ProfileStore, scanner: IndustryScanner,
                 matcher: SkillMatcher, analyzer: GapAnalyzer,
                 path_gen: LearningPathGenerator, action_gen: NextActionGenerator):
        self._profile_store = profile_store
        self._scanner = scanner
        self._matcher = matcher
        self._analyzer = analyzer
        self._path_gen = path_gen
        self._action_gen = action_gen
        self._panels = PanelStateManager()
        self._narrator = WorkbenchNarrator()

    # ── Main input handler (LLM-powered query rewriting) ──

    def handle_input(self, user_id: str, text: str) -> list[WorkbenchEvent]:
        """Parse user input with LLM, then route by intent.

        Replaces the old regex-based _extract_skills_from_text() and
        keyword-based _is_profile_input() with LLM NLU.
        """
        events: list[WorkbenchEvent] = []
        existing = self._profile_store.load()
        parsed = self._narrator.parse_user_input(text, existing)

        if parsed.intent == "confirm":
            # User is confirming — check which panel is ready for review
            for pid in ["profile", "direction", "gap", "path", "action"]:
                if self._panels.get_state(pid) == "READY_FOR_REVIEW":
                    events += self._panels.confirm(pid)
                    if pid == "profile":
                        events += self._run_match(user_id)
                    elif pid == "direction":
                        events += self._run_gap_analysis(user_id)
                    elif pid == "gap":
                        events += self._run_path_generation(user_id)
                    elif pid == "path":
                        events += self._run_next_action(user_id)
                    break

        elif parsed.intent == "profile_update":
            events += self._apply_parsed_profile(parsed)

        elif parsed.intent == "query":
            # User is asking a question — generate a narrator response
            ts = datetime.now(timezone.utc).isoformat()
            events.append(WorkbenchEvent(
                event_type="narrator.message",
                panel_id="",
                payload={
                    "type": "narrator",
                    "html": f"<p>{parsed.intent_summary or '请告诉我更多关于你的背景和职业目标，我来帮你分析适合的方向。'}</p>",
                    "intent": "query",
                },
                timestamp=ts,
            ))

        else:
            # Intent is "other" — treat as potential profile input, try extraction
            if parsed.skills or parsed.experiences:
                events += self._apply_parsed_profile(parsed)
            else:
                ts = datetime.now(timezone.utc).isoformat()
                events.append(WorkbenchEvent(
                    event_type="narrator.message",
                    panel_id="",
                    payload={
                        "type": "narrator",
                        "html": "<p>你好！我是 Crescent 职业规划助手。请告诉我你的技能、经历和职业兴趣，我来帮你找到最适合的发展方向。</p>",
                        "intent": "greeting",
                    },
                    timestamp=ts,
                ))

        return events

    def _apply_parsed_profile(self, parsed: ParsedInput) -> list[WorkbenchEvent]:
        """Apply LLM-parsed profile data to the store and update panel state."""
        events: list[WorkbenchEvent] = []

        if parsed.skills:
            self._profile_store.upsert_skills(parsed.skills)
        if parsed.experiences:
            profile = self._profile_store.load()
            for exp in parsed.experiences:
                profile.experiences.append(exp)
            self._profile_store.save(profile)
        if parsed.preferences and parsed.preferences.industry:
            profile = self._profile_store.load()
            profile.preferences = parsed.preferences
            self._profile_store.save(profile)
        if parsed.interests:
            profile = self._profile_store.load()
            existing = set(profile.interests)
            for interest in parsed.interests:
                if interest not in existing:
                    profile.interests.append(interest)
            self._profile_store.save(profile)
        if parsed.education:
            profile = self._profile_store.load()
            profile.education = parsed.education
            self._profile_store.save(profile)

        profile = self._profile_store.load()

        # Generate narrative profile payload via LLM
        narrative = self._narrator.narrate_profile(profile)

        state = "READY_FOR_REVIEW" if profile.skills else "PARTIAL"
        payload = {**narrative, "raw": profile.to_dict()}
        events += self._panels.set_state("profile", state, payload)

        return events

    # ── Pipeline chain ──

    def can_confirm(self, panel_id: str) -> bool:
        return self._panels.upstream_confirmed(panel_id)

    def confirm_panel(self, user_id: str, panel_id: str) -> list[WorkbenchEvent]:
        current_state = self._panels.get_state(panel_id)
        if current_state != "READY_FOR_REVIEW":
            return []
        if not self._panels.upstream_confirmed(panel_id):
            return []
        events = self._panels.confirm(panel_id)

        if panel_id == "profile" and self._panels.get_state("profile") == "CONFIRMED":
            events += self._run_match(user_id)
        elif panel_id == "direction" and self._panels.get_state("direction") == "CONFIRMED":
            events += self._run_gap_analysis(user_id)
        elif panel_id == "gap" and self._panels.get_state("gap") == "CONFIRMED":
            events += self._run_path_generation(user_id)
        elif panel_id == "path" and self._panels.get_state("path") == "CONFIRMED":
            events += self._run_next_action(user_id)

        return events

    def revoke_panel(self, user_id: str, panel_id: str, reason: str = "") -> list[WorkbenchEvent]:
        return self._panels.revoke(panel_id)

    # ── Pipeline stages (each calls narrator for narrative content) ──

    def _run_match(self, user_id: str) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        profile = self._profile_store.load()
        keywords = list(profile.skills.keys()) + profile.interests
        if not keywords:
            keywords = ["技术", "开发"]

        try:
            trends = self._scanner.scan(keywords)
        except Exception:
            trends = []

        if trends:
            ts = datetime.now(timezone.utc).isoformat()
            events.append(WorkbenchEvent(
                event_type="source.indexed",
                panel_id="source",
                payload={"sources": [{"type": s.source_type, "title": s.title}
                                     for t in trends for s in t.sources[:2]]},
                timestamp=ts,
            ))
            self._panels.set_state("source", "READY_FOR_REVIEW",
                                    {"source_count": len(trends)})

        matches = self._matcher.match(profile, trends) if trends else []
        if matches:
            # Generate narrative direction descriptions via LLM
            narrative = self._narrator.narrate_direction(matches, profile)

            ts = datetime.now(timezone.utc).isoformat()
            events.append(WorkbenchEvent(
                event_type="direction.matched",
                panel_id="direction",
                payload=narrative,
                timestamp=ts,
            ))
            self._panels.set_state("direction", "READY_FOR_REVIEW", narrative)

        return events

    def _run_gap_analysis(self, user_id: str) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        profile = self._profile_store.load()
        direction_payload = self._panels.get_payload("direction")
        top_direction = direction_payload.get("top_match", "")
        directions = direction_payload.get("directions", [])

        if not top_direction:
            return events

        # Reconstruct gap info from direction data
        first_dir = directions[0] if directions else {}
        gap_names = first_dir.get("gaps", [])
        overlap_names = first_dir.get("overlaps", [])

        dummy_match = MatchResult(
            direction=top_direction,
            score=direction_payload.get("top_score", 0),
            skill_overlap=overlap_names,
            skill_gap=gap_names,
            transferability=0.5,
            rationale="",
        )
        report = self._analyzer.analyze(profile, dummy_match)

        if report.gaps:
            # Generate narrative gap analysis via LLM
            narrative = self._narrator.narrate_gap(report.gaps, profile, top_direction)

            ts = datetime.now(timezone.utc).isoformat()
            events.append(WorkbenchEvent(
                event_type="gap.analyzed",
                panel_id="gap",
                payload=narrative,
                timestamp=ts,
            ))
            self._panels.set_state("gap", "READY_FOR_REVIEW", narrative)

        return events

    def _run_path_generation(self, user_id: str) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        profile = self._profile_store.load()
        from services.workbench.gap_analyzer import GapItem

        gap_payload = self._panels.get_payload("gap")
        gaps_raw = gap_payload.get("gaps", [])
        direction_payload = self._panels.get_payload("direction")
        top_direction = direction_payload.get("top_match", "")

        gaps = [GapItem(skill_name=g["skill"], required_level=g.get("required", "beginner"),
                         current_level=g.get("current", "none"), priority=g.get("priority", "medium"),
                         rationale=g.get("reason", ""))
                for g in gaps_raw]
        report = GapReport(gaps=gaps)
        path = self._path_gen.generate(report, profile)

        # Generate narrative path description via LLM
        narrative = self._narrator.narrate_path(gaps, profile, top_direction)

        ts = datetime.now(timezone.utc).isoformat()
        events.append(WorkbenchEvent(
            event_type="path.generated",
            panel_id="path",
            payload=narrative,
            timestamp=ts,
        ))
        self._panels.set_state("path", "READY_FOR_REVIEW", narrative)

        return events

    def _run_next_action(self, user_id: str) -> list[WorkbenchEvent]:
        events: list[WorkbenchEvent] = []
        path_payload = self._panels.get_payload("path")
        phases = path_payload.get("phases", [])
        if not phases:
            return events

        gap_payload = self._panels.get_payload("gap")
        gaps_raw = gap_payload.get("gaps", [])
        from services.workbench.gap_analyzer import GapItem
        gaps = [GapItem(skill_name=g["skill"], required_level=g.get("required", "beginner"),
                         current_level=g.get("current", "none"), priority=g.get("priority", "medium"),
                         rationale=g.get("reason", ""))
                for g in gaps_raw]

        # Generate narrative action items via LLM
        narrative = self._narrator.narrate_action(phases, gaps)

        ts = datetime.now(timezone.utc).isoformat()
        events.append(WorkbenchEvent(
            event_type="action.generated",
            panel_id="action",
            payload=narrative,
            timestamp=ts,
        ))
        self._panels.set_state("action", "READY_FOR_REVIEW", narrative)

        return events
