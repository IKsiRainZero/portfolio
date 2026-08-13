from __future__ import annotations
import json
import re
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput, IngestedDocument
from services.deepseek_client import chat


def _build_plan_prompt(query: str, docs: list[IngestedDocument]) -> str:
    """构建方案生成提示词，包含可信度标签和来源追溯。"""
    sources_text = "\n\n".join(
        f"### 来源 {i+1} [{d.structured.get('credibility_label', '未知') if d.structured else '未知'}]\n"
        f"URL: {d.source_url}\n"
        f"内容: {d.text[:600]}..."
        for i, d in enumerate(docs)
    )
    return f"""基于以下可信信息源，回答用户的问题并给出行动方案。

## 用户需求
"{query}"

## 可信信息源
{sources_text}

请输出一个结构化的行动方案。必须包含：
1. **最小可做行动** — 用户当下就能做的一件事，具体、可验证
2. **发展方案** — 分阶段的长期计划
3. **来源引用** — 每个建议的来源追溯

输出 JSON 格式：
{{
  "minimal_action": {{"what": "具体行动", "why": "为什么这是第一步", "steps": ["步骤1", "步骤2"], "estimated_time": "预估时间"}},
  "development_plan": {{"phases": [{{"name": "阶段名", "goal": "目标", "tasks": ["任务1"], "duration": "时间"}}]}},
  "sources": [{{"doc_id": "...", "key_claim": "引用的关键信息", "credibility": "高可信/存疑/需人工核实"}}],
  "confidence": 0.8,
  "caveats": ["需要注意的风险或假设"]
}}"""


def _parse_plan_response(response: str) -> dict | None:
    """解析 LLM 返回的方案 JSON，支持 markdown 代码块包裹。"""
    js = response.strip()
    if js.startswith("```"):
        js = re.sub(r"^```\w*\n?", "", js)
        js = re.sub(r"\n?```$", "", js)
    try:
        return json.loads(js)
    except json.JSONDecodeError:
        return None


class PlanGeneratorStep:
    """S5: 基于可信文档生成结构化方案。"""

    def __init__(self, name: str = "S5"):
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        return False

    def run(self, input: StepInput) -> StepOutput:
        # 从 S4 获取已标注可信度的文档
        docs: list[IngestedDocument] = input.previous_outputs.get("S4", {}).get("documents", [])
        # 如果没有 S4 输出，尝试从 S3_fetch 直接获取
        if not docs:
            docs = input.previous_outputs.get("S3_fetch", {}).get("documents", [])

        prompt = _build_plan_prompt(input.query, docs)

        try:
            reply, usage = chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一个战略顾问，基于可信信息输出可执行的行动方案。只输出 JSON。",
                temperature=0.3,
                max_tokens=1500,
                timeout=45,
            )
        except Exception as e:
            return StepOutput(
                step_name=self.name,
                status="error",
                data={"error": f"LLM call failed: {e}"},
                confidence=0.0,
            )

        plan = _parse_plan_response(reply)
        if plan is None:
            return StepOutput(
                step_name=self.name,
                status="error",
                data={"error": "Failed to parse plan JSON", "raw": reply[:500]},
                confidence=0.0,
            )

        return StepOutput(
            step_name=self.name,
            status="ok",
            data={"plan": plan, "token_usage": usage},
            confidence=plan.get("confidence", 0.7),
        )
