from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import requests
import feedparser

from services.pipeline.search import search_web, is_search_available
from services import arxiv_client
from config import ARXIV_SEARCH_MAX_RESULTS

HN_FEED = "https://hnrss.org/frontpage?count=20"
KR36_FEED = "https://36kr.com/feed"
GITHUB_TRENDING = "https://github.com/trending"


@dataclass
class Source:
    source_type: str    # "news" | "hn" | "github" | "arxiv" | "serpapi" | "36kr"
    title: str
    url: str
    snippet: str
    fetched_at: str


@dataclass
class SkillRequirement:
    skill_name: str
    importance: str     # "must" | "recommended" | "optional"
    frequency: int      # how many sources mention this skill


@dataclass
class SkillRequirementSet:
    skills: list[SkillRequirement]


@dataclass
class IndustryTrend:
    direction: str
    heat_score: float       # 0.0–1.0
    source_count: int
    skill_requirements: SkillRequirementSet
    trend_timeline: str     # "上升期" | "成熟期" | "衰退期"
    sources: list[Source] = field(default_factory=list)


class IndustryScanner:
    def scan(self, keywords: list[str]) -> list[IndustryTrend]:
        trends: list[IndustryTrend] = []
        now = datetime.now(timezone.utc).isoformat()

        query_str = " ".join(keywords[:4])

        # 1. HN RSS
        try:
            hn = feedparser.parse(HN_FEED)
            for entry in hn.entries[:15]:
                if self._match_keywords(entry.get("title", "") + entry.get("summary", ""), keywords):
                    trends.append(IndustryTrend(
                        direction=self._extract_direction(entry.get("title", ""), keywords),
                        heat_score=0.5,
                        source_count=1,
                        skill_requirements=SkillRequirementSet(skills=[]),
                        trend_timeline="上升期",
                        sources=[Source("hn", entry.get("title", ""), entry.get("link", ""),
                                         entry.get("summary", "")[:300], now)],
                    ))
        except (requests.RequestException, Exception):
            pass

        # 2. 36氪 RSS
        try:
            kr = feedparser.parse(KR36_FEED)
            for entry in kr.entries[:15]:
                if self._match_keywords(entry.get("title", "") + entry.get("summary", ""), keywords):
                    trends.append(IndustryTrend(
                        direction=self._extract_direction(entry.get("title", ""), keywords),
                        heat_score=0.5,
                        source_count=1,
                        skill_requirements=SkillRequirementSet(skills=[]),
                        trend_timeline="上升期",
                        sources=[Source("36kr", entry.get("title", ""), entry.get("link", ""),
                                         entry.get("summary", "")[:300], now)],
                    ))
        except (requests.RequestException, Exception):
            pass

        # 3. GitHub Trending
        try:
            resp = requests.get(GITHUB_TRENDING, timeout=10)
            if resp.status_code == 200:
                gh_trends = self._parse_github_trending(resp.text, keywords, now)
                trends.extend(gh_trends)
        except (requests.RequestException, Exception):
            pass

        # 4. ArXiv
        try:
            papers = arxiv_client.search(query_str, max_results=ARXIV_SEARCH_MAX_RESULTS)
            for p in papers:
                if self._match_keywords(p.get("title", "") + p.get("summary", ""), keywords):
                    trends.append(IndustryTrend(
                        direction=self._extract_direction(p.get("title", ""), keywords),
                        heat_score=0.4,
                        source_count=1,
                        skill_requirements=SkillRequirementSet(skills=[]),
                        trend_timeline="上升期",
                        sources=[Source("arxiv", p.get("title", ""), p.get("link", ""),
                                         p.get("summary", "")[:300], now)],
                    ))
        except (requests.RequestException, Exception):
            pass

        # 5. SerpAPI (定向搜索)
        if is_search_available():
            for kw in keywords[:2]:
                try:
                    results = search_web(f"{kw} industry trend career 2026", max_results=5)
                    for r in results:
                        trends.append(IndustryTrend(
                            direction=self._extract_direction(r.get("title", "") + r.get("snippet", ""), keywords),
                            heat_score=0.6,
                            source_count=1,
                            skill_requirements=SkillRequirementSet(skills=[]),
                            trend_timeline="上升期",
                            sources=[Source("serpapi", r.get("title", ""), r.get("url", ""),
                                             r.get("snippet", "")[:300], now)],
                        ))
                except (requests.RequestException, Exception):
                    continue

        return self._dedup_and_merge(trends)

    def get_skill_requirements(self, direction: str) -> SkillRequirementSet:
        skills: list[SkillRequirement] = []
        if is_search_available():
            try:
                results = search_web(f"{direction} required skills job description", max_results=10)
                skill_freq: dict[str, int] = {}
                for r in results:
                    snippet = (r.get("snippet", "") + r.get("title", "")).lower()
                    for kw in ["python", "java", "go", "rust", "sql", "ml", "ai",
                               "llm", "kubernetes", "docker", "react", "typescript",
                               "aws", "tensorflow", "pytorch", "langchain", "rag"]:
                        if kw in snippet:
                            skill_freq[kw] = skill_freq.get(kw, 0) + 1
                for name, freq in sorted(skill_freq.items(), key=lambda x: -x[1])[:10]:
                    imp = "must" if freq >= 3 else "recommended" if freq >= 1 else "optional"
                    skills.append(SkillRequirement(skill_name=name, importance=imp, frequency=freq))
            except (requests.RequestException, Exception):
                pass
        return SkillRequirementSet(skills=skills)

    def _match_keywords(self, text: str, keywords: list[str]) -> bool:
        t = text.lower()
        return any(kw.lower() in t for kw in keywords)

    def _extract_direction(self, title: str, keywords: list[str]) -> str:
        directions = {
            "ai agent": "AI Agent 开发", "agent": "AI Agent 开发",
            "llm": "LLM 应用开发", "大模型": "LLM 应用开发",
            "mlops": "MLOps", "machine learning": "ML/AI 工程",
            "data engineer": "数据工程", "data engineering": "数据工程",
            "backend": "后端开发", "full stack": "全栈开发",
            "cloud": "云基础设施", "kubernetes": "云基础设施",
            "cyber": "安全工程", "security": "安全工程",
        }
        t = title.lower()
        for kw, direction in directions.items():
            if kw in t:
                return direction
        return keywords[0] if keywords else "技术方向"

    def _parse_github_trending(self, html: str, keywords: list[str],
                                now: str) -> list[IndustryTrend]:
        trends: list[IndustryTrend] = []
        repos = html.count('<article')
        if repos == 0:
            return trends
        for kw in keywords:
            if kw.lower() in html.lower():
                trends.append(IndustryTrend(
                    direction=self._extract_direction(kw, [kw]),
                    heat_score=0.7,
                    source_count=1,
                    skill_requirements=SkillRequirementSet(skills=[]),
                    trend_timeline="上升期",
                    sources=[Source("github", f"{kw} trending", GITHUB_TRENDING,
                                     f"Mentions of {kw} in trending repos", now)],
                ))
        return trends

    def _dedup_and_merge(self, trends: list[IndustryTrend]) -> list[IndustryTrend]:
        grouped: dict[str, IndustryTrend] = {}
        for t in trends:
            key = t.direction.lower().strip()
            if key in grouped:
                grouped[key].source_count += 1
                grouped[key].sources.extend(t.sources)
                grouped[key].heat_score = max(grouped[key].heat_score, t.heat_score)
            else:
                grouped[key] = t
        merged = list(grouped.values())
        merged.sort(key=lambda x: x.heat_score * x.source_count, reverse=True)
        return merged[:10]
