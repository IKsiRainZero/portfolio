"""数据源模块单元测试"""
import sys
import atexit
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.data_sources.filters import (
    filter_sensitive, deduplicate, validate_schema, detect_drift
)
from services.data_sources.cache import save_cache, load_cache, get_stale_data, set_cache_dir

# 测试用临时缓存目录，防止污染真实 data/cache/
_test_cache_dir = Path(tempfile.mkdtemp(prefix="test_cache_"))
set_cache_dir(_test_cache_dir)
atexit.register(shutil.rmtree, _test_cache_dir, ignore_errors=True)


class TestFilters:
    def test_filter_sensitive_removes_blocked(self):
        items = [
            {"title": "正常新闻", "summary": "科技发展"},
            {"title": "赌博网站", "summary": "在线赌博平台"},
        ]
        clean = filter_sensitive(items)
        assert len(clean) == 1
        assert clean[0]["title"] == "正常新闻"

    def test_filter_sensitive_passes_all_clean(self):
        items = [
            {"title": "AI突破", "summary": "新模型发布"},
            {"title": "天气晴朗", "summary": "本周天气预报"},
        ]
        clean = filter_sensitive(items)
        assert len(clean) == 2

    def test_deduplicate_by_title(self):
        items = [
            {"title": "Same News", "url": "a.com"},
            {"title": "Same News", "url": "b.com"},
            {"title": "Other", "url": "c.com"},
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_validate_schema_checks_required(self):
        data = [
            {"title": "T1", "url": "a.com", "summary": "S1"},
            {"title": "T2", "url": "", "summary": ""},
        ]
        passed, errors = validate_schema(data, ("title", "url"))
        assert len(passed) == 1
        assert len(errors) == 1
        assert "url" in errors[0]

    def test_detect_drift_flags_schema_change(self):
        old_data = [{"title": "X", "url": "y"}]
        import hashlib, json
        old_keys = sorted(old_data[0].keys())
        old_hash = hashlib.sha256(json.dumps(old_keys).encode()).hexdigest()[:16]

        new_data = [{"title": "X", "url": "y", "author": "z"}]  # 多了 author
        assert detect_drift(new_data, old_hash) is True

    def test_detect_drift_no_change(self):
        data = [{"title": "X", "url": "y"}]
        import hashlib, json
        keys = sorted(data[0].keys())
        h = hashlib.sha256(json.dumps(keys).encode()).hexdigest()[:16]
        assert detect_drift(data, h) is False


class TestCache:
    def test_save_and_load(self):
        save_cache("_test", [{"a": 1}], "abc123", 1800)
        cached = load_cache("_test")
        assert cached is not None
        assert cached["data"] == [{"a": 1}]
        assert cached["ttl"] == 1800

    def test_get_stale_returns_even_expired(self):
        save_cache("_test_stale", [{"b": 2}], "xyz", -1)  # expired
        stale = get_stale_data("_test_stale")
        assert stale is not None
        assert stale["data"] == [{"b": 2}]

    def test_load_nonexistent_returns_none(self):
        assert load_cache("_nonexistent") is None


from unittest.mock import patch, MagicMock
from services.data_sources.news_source import NewsSource


class TestNewsSource:
    def test_health_check_ok(self):
        with patch("services.data_sources.news_source.requests.head") as mk:
            mk.return_value.status_code = 200
            ns = NewsSource()
            assert ns.health_check() is True

    def test_health_check_fail(self):
        with patch("services.data_sources.news_source.requests.head") as mk:
            mk.side_effect = Exception("timeout")
            ns = NewsSource()
            assert ns.health_check() is False

    def test_fetch_returns_articles(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "AI Breakthrough",
                    "source": {"name": "TechNews"},
                    "url": "https://example.com/1",
                    "description": "A new AI model.",
                    "publishedAt": "2026-06-23T10:00:00Z",
                }
            ],
        }
        with patch("services.data_sources.news_source.requests.get") as mk:
            mk.return_value = mock_resp
            mk.return_value.encoding = "utf-8"
            ns = NewsSource()
            articles = ns.fetch(categories=["technology"], count=5)
            assert len(articles) == 1
            assert articles[0]["title"] == "AI Breakthrough"

    def test_validate_removes_bad_schema(self):
        ns = NewsSource()
        raw = [
            {"title": "Good", "url": "https://a.com"},
            {"title": "", "url": ""},
        ]
        clean = ns.validate(raw)
        assert len(clean) == 1

    def test_format_for_agent_nonempty(self):
        ns = NewsSource()
        data = [{"title": "T", "source": "S", "summary": "sum", "url": "u"}]
        text = ns.format_for_agent(data)
        assert "T" in text
        assert "S" in text

    def test_format_for_agent_empty(self):
        ns = NewsSource()
        text = ns.format_for_agent([])
        assert "无可用" in text

    def test_get_briefs_fallback_to_cache(self):
        ns = NewsSource()
        # Pre-populate cache
        save_cache("news", [{"title": "Old", "url": "x"}], "hash1", 1800)
        # Make fetch fail
        with patch.object(ns, "fetch", side_effect=Exception("down")):
            briefs, stale, msg = ns.get_briefs(
                categories=["technology"], count=5
            )
            assert stale is True
            assert len(briefs) > 0
