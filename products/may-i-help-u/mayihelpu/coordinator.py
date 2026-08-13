import json
import os
import re
from pathlib import Path

# Auto-use HF mirror in China — must be set before sentence-transformers import
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from mayihelpu.context import ProblemContext, Resource
from mayihelpu.llm import LLMClient, get_default_client

GATHER_SYSTEM = """You are a technical resource curator. Given solution approaches, recommend specific, real resources.

Rules:
1. Recommend real libraries, documentation URLs, tutorials, or tools (not hypothetical)
2. Prefer official docs (docs.python.org, pypi.org, library docs) over blog posts
3. relevance is 0.0-1.0: how directly this resource helps implement the solution
4. Output a JSON object with key "resources" mapping solution-id to an array of 1-3 resources
5. Each resource has: id (kebab-case), url (full URL), summary (1 sentence what it provides), relevance (float 0.0-1.0)

Output ONLY the JSON object, no markdown, no explanation."""


class Coordinator:
    def __init__(self, llm: LLMClient | None = None, db_path: str = ""):
        self.llm = llm or get_default_client()
        self._db_path = db_path or str(Path(__file__).parent.parent / "data" / "chroma_db")
        self._embed_model = None
        self._client = None
        self._collection = None

    # ── public API ──

    def gather(self, ctx: ProblemContext, query: str = "") -> ProblemContext:
        ctx.log("Coordinator", f"gather query={query or 'auto'} solutions={len(ctx.solutions)}", "")
        if not ctx.solutions:
            return ctx

        solutions_by_id = {s.id: s for s in ctx.solutions}
        resources = self._gather_batch(list(solutions_by_id.items()))
        self._index_resources(resources)
        ctx.resources.extend(resources)
        ctx.log("Coordinator", "done", f"{len(ctx.resources)} resources indexed")
        return ctx

    def web_search(self, query: str, max_results: int = 5) -> list[Resource]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        layers = self._detect_intent(query)
        all_resources: list[Resource] = []

        layer_map = {
            "docs": self._search_docs,
            "qa": self._search_qa,
            "generic": self._search_generic,
            "code": self._search_code,
            "bilibili": self._search_bilibili,
        }

        active = {k: v for k, v in layer_map.items() if k in layers}
        results_by_layer: dict[str, list[Resource]] = {}

        with ThreadPoolExecutor(max_workers=len(active)) as pool:
            futures = {pool.submit(fn, query, max_results): name for name, fn in active.items()}
            try:
                for future in as_completed(futures, timeout=45):
                    name = futures[future]
                    try:
                        results_by_layer[name] = future.result() or []
                    except Exception:
                        results_by_layer[name] = []
            except TimeoutError:
                for name, future in futures.items():
                    if name not in results_by_layer:
                        results_by_layer[name] = []

        for name in ["docs", "qa", "generic", "code", "bilibili"]:
            if name in results_by_layer:
                all_resources.extend(results_by_layer[name])

        if not all_resources:
            return [Resource(id="web-search-empty", url="", summary=f"No results for: {query}", relevance=0.0)]
        return all_resources

    def _search_generic(self, query: str, max_results: int = 5) -> list[Resource]:
        resources = self._serpapi_search(query, max_results)
        if not resources:
            resources = self._bing_search(query, max_results)
        detail_pages = resources[:3]
        for r in detail_pages:
            if r.url and not r.summary.startswith("[score="):
                detail = self._fetch_and_summarize(r.url, query)
                if detail:
                    r.summary = detail
        return resources

    def _serpapi_search(self, query: str, max_results: int = 5) -> list[Resource]:
        import urllib.request
        from urllib.parse import quote, urlencode
        api_key = os.environ.get("SERPAPI_KEY", "")
        if not api_key:
            return []
        params = urlencode({
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": str(max_results),
        })
        url = f"https://serpapi.com/search?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mayihelpu/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            resources: list[Resource] = []
            for i, result in enumerate(data.get("organic_results", [])[:max_results]):
                title = result.get("title", "")
                link = result.get("link", "")
                snippet = result.get("snippet", "")
                rid = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")[:40])
                resources.append(Resource(
                    id=f"serp-{rid}",
                    url=link,
                    summary=f"{title}. {snippet}"[:300],
                    relevance=round(0.95 - i * 0.05, 2),
                ))
            return resources
        except Exception:
            return []

    def _bing_search(self, query: str, max_results: int = 5) -> list[Resource]:
        from urllib.parse import quote
        from scrapling.fetchers import Fetcher

        url = f"https://cn.bing.com/search?q={quote(query)}"
        try:
            resp = Fetcher.get(url, timeout=15)
        except Exception:
            return []

        resources: list[Resource] = []
        for i, el in enumerate(resp.css(".b_algo")[:max_results]):
            links = el.css("h2 a")
            if not links:
                continue
            link = links[0]
            href = link.attrib.get("href", "")
            title = (link.get_all_text() or "").strip()
            snippet_els = el.css(".b_caption p")
            desc = (snippet_els[0].get_all_text() or "").strip()[:300] if snippet_els else ""

            if href and title:
                rid = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")[:40])
                resources.append(Resource(
                    id=f"web-{rid}",
                    url=href,
                    summary=f"{title}. {desc}" if desc else title,
                    relevance=round(0.95 - i * 0.05, 2),
                ))
        return resources

    def _search_code(self, query: str, max_results: int = 5) -> list[Resource]:
        import subprocess
        resources: list[Resource] = []
        try:
            r = subprocess.run(
                ["gh", "search", "code", query, "--limit", str(max_results), "--json", "repository,path,url"],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode != 0:
                return []
            data = json.loads(r.stdout)
            for i, item in enumerate(data[:max_results]):
                repo = item.get("repository", {}).get("fullName", "unknown")
                path = item.get("path", "")
                url = item.get("url", "")
                rid = re.sub(r"[^a-z0-9-]", "", f"gh-{repo}-{path}"[:40])
                resources.append(Resource(
                    id=rid,
                    url=url,
                    summary=f"GitHub: {repo}/{path}",
                    relevance=round(0.80 - i * 0.05, 2),
                ))
        except (FileNotFoundError, Exception):
            pass
        return resources

    def _search_bilibili(self, query: str, max_results: int = 3) -> list[Resource]:
        import asyncio
        resources: list[Resource] = []

        async def _do():
            try:
                from bilibili_api import search, video, Credential
            except ImportError:
                return []
            try:
                sr = await search.search_by_type(
                    query, search_type=search.SearchObjectType.VIDEO,
                    page=1,
                )
            except Exception:
                return []
            results: list[Resource] = []
            items = sr.get("result", [])[:max_results]
            for i, item in enumerate(items):
                bvid = item.get("bvid", "")
                title = item.get("title", "")
                author = item.get("author", "")
                arcurl = item.get("arcurl", "") or f"https://www.bilibili.com/video/{bvid}"
                if not bvid:
                    continue
                subtitle_text = ""
                try:
                    v = video.Video(bvid=bvid, credential=Credential())
                    info = await v.get_info()
                    cid = info.get("cid") or (info.get("pages", [{}])[0].get("cid") if info.get("pages") else None)
                    if cid:
                        subs = await v.get_subtitle(cid)
                        if subs and subs.get("subtitles"):
                            sub_url = subs["subtitles"][0].get("subtitle_url", "")
                            if sub_url and sub_url.startswith("http"):
                                import urllib.request
                                req = urllib.request.Request(sub_url, headers={"User-Agent": "mayihelpu/0.1"})
                                with urllib.request.urlopen(req, timeout=10) as resp:
                                    sub_data = json.loads(resp.read().decode("utf-8"))
                                lines = [b.get("content", "") for b in sub_data.get("body", [])]
                                subtitle_text = " ".join(lines)[:4000]
                except Exception:
                    pass
                if subtitle_text:
                    try:
                        prompt = (
                            f"Query: {query}\n\n"
                            f"Video transcript ({title} by {author}):\n{subtitle_text}\n\n"
                            "Extract information directly relevant to the query. "
                            "Return 2-3 concise sentences. If nothing is relevant, return NOT_RELEVANT."
                        )
                        summary = self.llm.chat(
                            system="Extract relevant technical information from video transcripts.",
                            user=prompt,
                            temperature=0.1,
                            max_tokens=300,
                        )
                        if summary.strip() == "NOT_RELEVANT" or not summary.strip():
                            summary = f"[B站] {title} by {author} (subtitle extracted, no relevant content found)"
                    except Exception:
                        summary = f"[B站] {title} by {author}"
                else:
                    summary = f"[B站] {title} by {author}"
                rid = re.sub(r"[^a-z0-9-]", "", f"bili-{bvid}"[:40])
                results.append(Resource(
                    id=rid,
                    url=arcurl,
                    summary=summary[:400],
                    relevance=round(0.80 - i * 0.05, 2),
                ))
            return results

        try:
            resources = asyncio.run(_do())
        except Exception:
            pass
        return resources or []

    def _detect_intent(self, query: str) -> set[str]:
        q = query.lower()
        layers = {"docs", "qa", "generic"}
        code_triggers = {"error", "bug", "issue", "traceback", "exception", "stack trace",
                         "github", "source code", "repo", "commit", "pull request"}
        video_triggers = {"教程", "视频", "demo", "演示", "bv", "bilibili", "b站",
                          "tutorial", "walkthrough", "youtube"}
        if any(t in q for t in code_triggers):
            layers.add("code")
        if any(t in q for t in video_triggers):
            layers.add("bilibili")
        return layers

    def _search_docs(self, query: str, max_results: int = 5) -> list[Resource]:
        import urllib.request
        resources: list[Resource] = []
        q = query.strip().lower().replace(" ", "+")
        pypi_url = f"https://pypi.org/search/?q={q}"

        try:
            req = urllib.request.Request(pypi_url, headers={"User-Agent": "mayihelpu/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            from html.parser import HTMLParser

            class PyPIParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.packages: list[dict] = []
                    self._in_link = False
                    self._in_desc = False
                    self._cur: dict = {}
                    self._tag = ""

                def handle_starttag(self, tag, attrs):
                    d = dict(attrs)
                    cls = d.get("class", "")
                    if tag == "a" and "package-snippet" in cls:
                        self._in_link = True
                        self._cur = {"name": "", "url": "https://pypi.org" + d.get("href", ""), "desc": ""}
                    elif tag == "span" and "package-snippet__name" in cls:
                        self._tag = "name"
                    elif tag == "p" and "package-snippet__description" in cls:
                        self._in_desc = True

                def handle_data(self, data):
                    if self._tag == "name" and self._cur:
                        self._cur["name"] = data.strip()
                        self._tag = ""
                    if self._in_desc and self._cur:
                        self._cur["desc"] = data.strip()[:200]
                        self._in_desc = False

                def handle_endtag(self, tag):
                    if tag == "a" and self._in_link:
                        self._in_link = False
                        if self._cur.get("name"):
                            self.packages.append(self._cur)
                        self._cur = {}

            parser = PyPIParser()
            parser.feed(html)
            for i, pkg in enumerate(parser.packages[:max_results]):
                rid = re.sub(r"[^a-z0-9-]", "", pkg["name"].lower()[:30])
                resources.append(Resource(
                    id=f"pypi-{rid}",
                    url=pkg["url"],
                    summary=pkg["desc"] or pkg["name"],
                    relevance=round(0.90 - i * 0.05, 2),
                ))
        except Exception:
            pass
        return resources

    def _search_qa(self, query: str, max_results: int = 5) -> list[Resource]:
        import urllib.request
        from urllib.parse import quote, urlencode
        resources: list[Resource] = []
        params = urlencode({
            "order": "desc",
            "sort": "relevance",
            "q": query,
            "site": "stackoverflow",
            "pagesize": str(max_results),
        })
        url = f"https://api.stackexchange.com/2.3/search/advanced?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mayihelpu/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for i, item in enumerate(data.get("items", [])[:max_results]):
                rid = f"so-{item.get('question_id', i)}"
                title = item.get("title", "")
                link = item.get("link", "")
                score = item.get("score", 0)
                tags = ", ".join(item.get("tags", [])[:5])
                resources.append(Resource(
                    id=rid,
                    url=link,
                    summary=f"[score={score}] {title} | tags: {tags}",
                    relevance=round(0.85 - i * 0.05, 2),
                ))
        except Exception:
            pass
        return resources

    def _fetch_and_summarize(self, url: str, query: str) -> str:
        try:
            from scrapling.fetchers import Fetcher
            resp = Fetcher.get(url, timeout=10)
        except Exception:
            return ""
        body = resp.css("body")
        if not body:
            return ""
        text = body[0].get_all_text()
        text = text[:8000] if text else ""
        if len(text) < 100:
            return ""
        try:
            prompt = (
                f"Query: {query}\n\n"
                f"Page content from {url}:\n{text}\n\n"
                "Extract information directly relevant to the query. "
                "Return 2-3 concise sentences. If the page has no relevant information, return NOT_RELEVANT."
            )
            summary = self.llm.chat(
                system="Extract technical information from web pages relevant to a query. Be concise.",
                user=prompt,
                temperature=0.1,
                max_tokens=300,
            )
            if summary.strip() == "NOT_RELEVANT" or not summary.strip():
                return ""
            return summary.strip()
        except Exception:
            return ""

    def local_search(self, query: str, top_k: int = 5) -> list[Resource]:
        col = self._get_collection()
        if col.count() == 0:
            return []
        embedding = self._embed(query)
        results = col.query(query_embeddings=[embedding], n_results=min(top_k, col.count()))
        return self._hits_to_resources(results)

    def match(self, need: str, resources: list[Resource]) -> list[Resource]:
        if not resources:
            return []
        import numpy as np
        need_vec = np.array(self._embed(need))
        scored: list[tuple[float, Resource]] = []
        for r in resources:
            r_vec = np.array(self._embed(f"{r.id}: {r.summary} {r.url}"))
            sim = float(np.dot(need_vec, r_vec) / (np.linalg.norm(need_vec) * np.linalg.norm(r_vec) + 1e-8))
            r.relevance = round(sim, 3)
            scored.append((sim, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]

    # ── backends ──

    def _index_resources(self, resources: list[Resource]):
        if not resources:
            return
        col = self._get_collection()
        texts = [f"{r.id}: {r.summary} {r.url}" for r in resources]
        embeddings = [self._embed(t) for t in texts]
        try:
            col.add(
                ids=[r.id for r in resources],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{"url": r.url, "summary": r.summary, "relevance": r.relevance} for r in resources],
            )
        except Exception:
            # Duplicate ids — upsert instead
            col.upsert(
                ids=[r.id for r in resources],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{"url": r.url, "summary": r.summary, "relevance": r.relevance} for r in resources],
            )

    def _embed(self, text: str) -> list[float]:
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embed_model.encode(text, normalize_embeddings=True).tolist()

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            Path(self._db_path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self._db_path)
            self._collection = self._client.get_or_create_collection(
                name="session_resources",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _hits_to_resources(self, results: dict) -> list[Resource]:
        resources: list[Resource] = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for i, rid in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else 0.0
            resources.append(Resource(
                id=rid,
                url=meta.get("url", ""),
                summary=meta.get("summary", ""),
                relevance=round(1.0 - dist, 3),  # cosine distance → similarity
            ))
        return resources

    # ── LLM helpers ──

    def _gather_batch(self, solutions: list[tuple[str, object]]) -> list[Resource]:
        sol_list = "\n".join(
            f"- {sid}: {sol.method[:120]}" for sid, sol in solutions
        )
        user_prompt = f"Solutions needing resources:\n{sol_list}\n\nRecommend real resources for each solution id."
        response = self.llm.chat(system=GATHER_SYSTEM, user=user_prompt, temperature=0.3)
        data = self._parse(response)

        resources: list[Resource] = []
        res_map = data.get("resources", {}) if isinstance(data, dict) else {}
        for _, items in res_map.items():
            for item in items:
                resources.append(Resource(
                    id=item.get("id", ""),
                    url=item.get("url", ""),
                    summary=item.get("summary", ""),
                    relevance=float(item.get("relevance", 0.5)),
                ))
        return resources

    def _parse(self, response: str) -> dict | list:
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*", "", response)
            response = re.sub(r"\s*```$", "", response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {}
