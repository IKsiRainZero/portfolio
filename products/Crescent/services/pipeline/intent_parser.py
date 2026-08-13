from __future__ import annotations
import json
import re
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput, StepSpec, PipelineSpec
from services.deepseek_client import chat

ALL_STEPS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]

STEP_DESCRIPTIONS = {
    "S1": "意图解析 — 已完成（本步）",
    "S2": "资源盘点 — 扫描本地文件和知识库，了解已有资产",
    "S3": "信息摄取 — 搜索公网并抓取网页内容",
    "S4": "可信度融合 — 多源信息交叉验证与可信度标注",
    "S5": "方案生成 — 基于可信信息生成最小可做行动 + 发展方案",
    "S6": "追问循环 — 不确定的假设反问用户确认",
    "S7": "持久沉淀 — 决策记录入库，知识图谱更新",
}


def build_intent_prompt(query: str) -> str:
    steps_desc = "\n".join(f"- {k}: {v}" for k, v in STEP_DESCRIPTIONS.items())
    return f"""你是一个智能管道的意图解析器。用户会用自然语言描述需求，你需要决定 PipelineSpec 配置。
PipelineSpec 决定启用哪些步骤、步骤配置以及是否需要人工确认。

可用步骤：
{steps_desc}

用户需求："{query}"

请决定：
1. 哪些步骤需要启用（enabled: true/false）
2. 每个启用步骤的配置参数 (config)
3. 哪些步骤需要等待用户确认 (needs_human: true)

规则：
- 信息类问题（"什么是X"）→ S3(搜索) + S5(生成)，S2/S6通常跳过
- 调研类问题（"帮我调研X"）→ 启用 S2+S3+S4+S5，S6可选
- 行动建议类（"我该怎么做X"）→ 全管道 S1-S7
- S1 永远 enabled=true
- 输出必须是严格的 JSON 格式

请只输出 JSON（不要有其他文字）："""


def _parse_llm_response(response: str, query: str) -> PipelineSpec | None:
    """从 LLM 回复中提取 JSON 并构建 PipelineSpec。失败返回 None。"""
    js = response.strip()
    if js.startswith("```"):
        js = re.sub(r"^```\w*\n?", "", js)
        js = re.sub(r"\n?```$", "", js)
    try:
        data = json.loads(js)
    except json.JSONDecodeError:
        return None

    steps = []
    for s in data.get("steps", []):
        steps.append(StepSpec(
            step_name=s.get("step_name", ""),
            enabled=s.get("enabled", True),
            needs_human=s.get("needs_human", False),
            config=s.get("config", {}),
        ))
    # 确保所有 7 步都有定义
    existing = {s.step_name for s in steps}
    for name in ALL_STEPS:
        if name not in existing:
            steps.append(StepSpec(step_name=name, enabled=False))

    from datetime import datetime, timezone
    return PipelineSpec(
        steps=sorted(steps, key=lambda x: x.step_name),
        version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


class IntentParserStep:
    """S1: 将用户自然语言需求解析为 PipelineSpec。"""

    def __init__(self, name: str = "S1"):
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        return False  # S1 永远执行

    def run(self, input: StepInput) -> StepOutput:
        prompt = build_intent_prompt(input.query)
        try:
            reply, usage = chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是管道意图解析器。只输出 JSON。",
                temperature=0.1,
                max_tokens=800,
                timeout=30,
            )
        except Exception as e:
            return StepOutput(
                step_name=self.name, status="error",
                data={"error": f"LLM call failed: {e}"}, confidence=0.0,
            )

        spec = _parse_llm_response(reply, input.query)
        if spec is None:
            return StepOutput(
                step_name=self.name, status="error",
                data={"error": "Failed to parse LLM response as JSON", "raw_response": reply[:500]},
                confidence=0.0,
            )

        return StepOutput(
            step_name=self.name,
            status="ok",
            data={"pipeline_spec": spec, "token_usage": usage},
            confidence=0.85,
        )
