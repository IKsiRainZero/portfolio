import json
from unittest.mock import patch, MagicMock
from services.workbench.industry_scanner import (
    IndustryScanner, IndustryTrend, SkillRequirementSet,
    SkillRequirement, Source,
)


def _fake_serpapi_results(query, max_results):
    return [{"url": "https://example.com/ai-jobs", "title": "AI Jobs Rising",
             "snippet": "AI agent development is booming in 2026."}]

def _fake_arxiv_results(query, max_results):
    return [{"title": "LLM Agents Survey", "summary": "A survey of LLM-based agents.",
             "link": "https://arxiv.org/abs/1234.5678"}]

def _fake_hn_feed():
    return {
        "entries": [
            {"title": "AI Agents Take Over Backend", "link": "https://news.ycombinator.com/item?id=1",
             "summary": "Discussion about AI agents replacing traditional backends."},
        ]
    }

def _fake_36kr_feed():
    return {
        "entries": [
            {"title": "大模型创业公司融资10亿", "link": "https://36kr.com/p/123",
             "summary": "AI agent赛道持续火热。"},
        ]
    }

class TestIndustryScanner:
    @patch("services.workbench.industry_scanner.search_web")
    @patch("services.workbench.industry_scanner.arxiv_client")
    @patch("services.workbench.industry_scanner.feedparser")
    @patch("services.workbench.industry_scanner.requests.get")
    def test_scan_returns_trends(self, mock_requests_get, mock_feedparser,
                                  mock_arxiv, mock_search):
        mock_search.side_effect = _fake_serpapi_results
        mock_arxiv.search.return_value = _fake_arxiv_results("", 0)
        mock_feedparser.parse.side_effect = [_fake_hn_feed(), _fake_36kr_feed()]
        gh_resp = MagicMock()
        gh_resp.text = ('<article class="Box-row"><h2><a href="/user/repo">AI agent framework</a></h2></article>'
                        * 5)
        gh_resp.status_code = 200
        mock_requests_get.return_value = gh_resp

        scanner = IndustryScanner()
        trends = scanner.scan(["AI agent", "backend"])

        assert len(trends) > 0
        for t in trends:
            assert t.direction
            assert 0.0 <= t.heat_score <= 1.0
            assert t.source_count > 0

    @patch("services.workbench.industry_scanner.search_web")
    @patch("services.workbench.industry_scanner.arxiv_client")
    @patch("services.workbench.industry_scanner.feedparser")
    @patch("services.workbench.industry_scanner.requests.get")
    def test_scan_no_results_returns_empty(self, mock_requests_get, mock_feedparser,
                                            mock_arxiv, mock_search):
        mock_search.return_value = []
        mock_arxiv.search.return_value = []
        mock_feedparser.parse.return_value = MagicMock(entries=[])
        mock_requests_get.return_value = MagicMock(status_code=200, text="")
        scanner = IndustryScanner()
        trends = scanner.scan(["xyznonexistent"])
        assert len(trends) == 0

    def test_direction_dedup_merges_sources(self):
        s1 = Source("news", "Title A", "http://a.com", "about AI agents", "2026-01-01")
        s2 = Source("paper", "Title B", "http://b.com", "AI agents survey", "2026-01-02")
        scanner = IndustryScanner()
        trends = scanner._dedup_and_merge([
            IndustryTrend(direction="AI Agent Dev", heat_score=0.5, source_count=1,
                          skill_requirements=SkillRequirementSet(skills=[]),
                          trend_timeline="上升期", sources=[s1]),
            IndustryTrend(direction="AI Agent Dev", heat_score=0.7, source_count=1,
                          skill_requirements=SkillRequirementSet(skills=[]),
                          trend_timeline="上升期", sources=[s2]),
        ])
        assert len(trends) == 1
        assert trends[0].source_count == 2
        assert len(trends[0].sources) == 2
