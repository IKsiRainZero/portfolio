from __future__ import annotations
import json
from openai import AsyncOpenAI
from app.config import Config
from app.models import Entry, Layer, Dimension

DIAGNOSIS_PROMPT = """你是思维诊断助手。用户在思考「{question}」。

当前层级：{layer_name}（{layer_desc}）

用户在这一层已有的认知：
{known_entries}
未知缺口：
{unknown_entries}
待解答问题：
{question_entries}

请诊断：
1. 这一层跟「{question}」有什么关系？
2. 用户在这一层的认知中存在什么缺口？
3. 建议用户在这一层补充什么知识或提出什么问题？

输出严格 JSON（不要 markdown 代码块）：
{{"relation": "...", "gaps": ["...", "..."], "suggestions": ["...", "..."], "new_questions": ["...", "..."]}}"""

class DiagnosisService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)

    async def run(self, question: str, dimension_id: str, db):
        dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
        if not dim:
            yield {"event": "error", "data": json.dumps({"message": "Dimension not found"})}
            return

        layers = db.query(Layer).filter(Layer.dimension_id == dimension_id).order_by(Layer.level).all()
        all_results = []

        for layer in layers:
            yield {"event": "layer_start", "data": json.dumps({"level": layer.level, "name": layer.name})}

            entries = db.query(Entry).filter(Entry.layer_id == layer.id, Entry.status == "confirmed").all()
            known = [e.title for e in entries if e.entry_type == "known"]
            unknown = [e.title for e in entries if e.entry_type == "unknown"]
            questions = [e.title for e in entries if e.entry_type == "question"]

            prompt = DIAGNOSIS_PROMPT.format(
                question=question,
                layer_name=layer.name,
                layer_desc=layer.description or "",
                known_entries="\n".join(f"- {k}" for k in known) if known else "（无）",
                unknown_entries="\n".join(f"- {u}" for u in unknown) if unknown else "（无）",
                question_entries="\n".join(f"- {q}" for q in questions) if questions else "（无）",
            )

            try:
                response = await self.client.chat.completions.create(
                    model=Config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500,
                    timeout=30,
                )
                raw = response.choices[0].message.content or "{}"
                parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"level": layer.level, "message": str(e)})}
                parsed = {"relation": "", "gaps": [], "suggestions": [], "new_questions": []}

            result = {
                "level": layer.level,
                "name": layer.name,
                "relation": parsed.get("relation", ""),
                "gaps": parsed.get("gaps", []),
                "suggestions": parsed.get("suggestions", []),
                "new_questions": parsed.get("new_questions", []),
                "existing_entries_highlighted": [e.id for e in entries],
                "new_suggested_entries": [
                    {"title": q, "entry_type": "unknown", "content": ""}
                    for q in parsed.get("new_questions", [])
                ],
            }
            all_results.append(result)
            yield {"event": "layer_complete", "data": json.dumps(result, ensure_ascii=False)}

        gap_summary = self._summarize_gaps(all_results)
        yield {"event": "diagnose_end", "data": json.dumps({
            "question": question,
            "dimension": dim.name,
            "layers": all_results,
            "gap_summary": gap_summary,
        }, ensure_ascii=False)}

    def _summarize_gaps(self, results: list[dict]) -> str:
        empty_layers = [r["name"] for r in results if not r["relation"] and not r["gaps"]]
        gap_layers = [r["name"] for r in results if r["gaps"]]
        if empty_layers:
            return f"层级 {', '.join(empty_layers)} 几乎空白，建议优先探索。缺口集中在 {', '.join(gap_layers) if gap_layers else '暂无'}。"
        return f"缺口分布在 {', '.join(gap_layers)} 等层级。"
