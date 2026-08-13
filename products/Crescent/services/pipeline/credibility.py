from __future__ import annotations
import json
import re
from services.pipeline.types import StepInput, StepOutput, IngestedDocument
from services.deepseek_client import chat

# ── 常量 ──

RELATION_LABELS = ("一致", "互补", "分歧", "矛盾", "缺失")

CREDIBILITY_LABELS = ("高可信", "存疑", "需人工核实", "孤立无佐证")

# 关系标签 → 可信度标签映射
_RELATION_TO_CREDIBILITY: dict[str, str] = {
    "一致": "高可信",
    "互补": "高可信",
    "分歧": "存疑",
    "矛盾": "需人工核实",
    "缺失": "孤立无佐证",
}

# 可信度标签 → 分数映射
_CREDIBILITY_SCORES: dict[str, float] = {
    "高可信": 0.85,
    "存疑": 0.5,
    "需人工核实": 0.3,
    "孤立无佐证": 0.2,
}


# ── 算子 1: 源间关系分类 ──

def _build_relation_prompt(docs: list[IngestedDocument]) -> str:
    doc_texts = "\n\n---\n\n".join(
        f"文档{i+1} (来源: {d.source_url}):\n{d.text[:500]}"
        for i, d in enumerate(docs)
    )
    return f"""分析以下多篇文档之间的信息关系。

文档内容：
{doc_texts}

请对每对文档判断它们的信息关系，使用以下五类标签：

- 一致: 两篇文档的核心主张或关键事实相同，仅措辞或表达角度不同
- 互补: 两篇文档讨论同一大主题下的不同子话题或不同方面（如编码器 vs 解码器），合并后信息更全面
- 分歧: 两篇文档谈论同一话题下的不同细节或维度（如加速性能 vs 油耗），信息不同但不构成逻辑冲突
- 矛盾: 两篇文档就同一具体事实给出对立结论（如加速时间6.5s vs 8.2s），无法同时成立
- 缺失: 两篇文档讨论的主题完全不同（如Transformer vs 巴黎旅游），一篇的信息对另一篇的论题几乎没有参考价值

边界区分指南：
- 分歧 vs 互补：同一事物的不同方面（车的加速和油耗）→分歧；同一大领域的不同子话题（编码器和解码器）→互补
- 缺失 vs 互补：主题完全不同、没有交集（CNN和巴黎）→缺失；同一个技术体系内不同组件（CNN和池化层）→互补
- 分歧 vs 矛盾：同一事实的不同数据（加速6.5s vs 8.2s）→矛盾；不同事实的各自描述（加速和油耗）→分歧

参考示例：

示例1（一致）:
文档A: "Transformer使用自注意力机制并行处理序列"
文档B: "The Transformer relies on self-attention for parallel processing"
标签: 一致

示例2（分歧—同一主题下的不同维度，不构成直接冲突）:
文档A: "该研究提出的模型在基准测试中取得了最高分"
文档B: "对该研究的复现分析发现，其评估方法存在偏差"
标签: 分歧（两篇研究同一工作的不同维度，不是同一事实的对立，不构成矛盾）

示例3（矛盾—就同一事实给出冲突数据）:
文档A: "该车型百公里加速时间为6.5秒"
文档B: "测试表明该车型百公里加速需要8.2秒"
标签: 矛盾（两篇就同一事实——加速时间——给出冲突的数据，无法同时成立）

示例4（缺失—完全不同的话题）:
文档A: "Transformer使用自注意力机制处理序列"
文档B: "巴黎是法国的首都，以埃菲尔铁塔闻名"
标签: 缺失

请输出 JSON，不要包含其他内容：
{{"label": "一致", "confidence": 0.9, "rationale": "一句中文理由"}}"""


def classify_relation(doc_a: IngestedDocument, doc_b: IngestedDocument) -> dict:
    """两文档关系分类。失败时返回 '缺失' 默认值，绝不抛出异常。"""
    prompt = _build_relation_prompt([doc_a, doc_b])
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是多源信息关系分析助手。只输出 JSON，不要其他内容。",
            temperature=0.1,
            max_tokens=300,
            timeout=20,
        )
        js = reply.strip()
        if js.startswith("```"):
            js = re.sub(r"^```\w*\n?", "", js)
            js = re.sub(r"\n?```$", "", js)
        data = json.loads(js)
        label = data.get("label", "缺失")
        # 防御：确保 label 是合法值
        if label not in RELATION_LABELS:
            label = "缺失"
        return {
            "label": label,
            "confidence": float(data.get("confidence", 0.0)),
            "rationale": str(data.get("rationale", "LLM 返回格式异常")),
        }
    except Exception:
        return {"label": "缺失", "confidence": 0.0, "rationale": "LLM 异常"}


class SourceRelationClassifier:
    """算子 1: 对 IngestedDocument 列表做两两关系分类。"""
    name = "source_relation"

    def apply(self, docs: list[IngestedDocument]) -> list[dict]:
        if len(docs) < 2:
            return []
        results: list[dict] = []
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                r = classify_relation(docs[i], docs[j])
                r["doc_a_id"] = docs[i].id
                r["doc_b_id"] = docs[j].id
                results.append(r)
        return results


# ── 算子 2: 集合级充分性判据 ──

def _build_sufficiency_prompt(docs: list[IngestedDocument], query: str) -> str:
    doc_summaries = "\n".join(
        f"- 文档{i+1}: {d.text[:300]}..." for i, d in enumerate(docs)
    )
    return f"""评估以下文档集合是否能充分回答用户的问题。

用户问题："{query}"

已有文档摘要：
{doc_summaries}

请判断：
1. 这些文档是否充分覆盖了回答该问题所需的维度？
2. 如果不够充分，缺少哪些维度？

参考示例：

示例1:
用户问题: "Transformer的主要创新是什么"
已有文档: "Transformer完全依赖自注意力机制，放弃了循环和卷积结构"
输出: {{"sufficient": true, "missing_dimensions": [], "confidence": 0.9, "rationale": "单文档已足够回答核心创新"}}

示例2:
用户问题: "对比ResNet和DenseNet在ImageNet上的性能"
已有文档: "ResNet通过残差连接解决了深层网络的退化问题"
输出: {{"sufficient": false, "missing_dimensions": ["DenseNet的性能数据", "ImageNet上的对比实验"], "confidence": 0.7, "rationale": "缺少DenseNet的信息和对比数据"}}

示例3:
用户问题: "BERT模型的训练成本和推理速度"
已有文档: "BERT使用了掩码语言模型进行预训练，在GLUE上达到SOTA"
输出: {{"sufficient": false, "missing_dimensions": ["训练成本的具体数据", "推理速度"], "confidence": 0.6, "rationale": "仅介绍了模型机制，缺少成本和速度信息"}}

请输出 JSON，不要包含其他内容：
{{"sufficient": true/false, "missing_dimensions": ["维度1", ...], "confidence": 0.8, "rationale": "一句中文理由"}}"""


def assess_sufficiency(docs: list[IngestedDocument], query: str) -> dict:
    """集合级充分性判据。空文档直接返回不充分。失败时返回默认值，绝不抛出异常。"""
    if not docs:
        return {
            "sufficient": False,
            "missing_dimensions": ["无任何文档"],
            "confidence": 1.0,
            "rationale": "无文档可评估",
        }
    prompt = _build_sufficiency_prompt(docs, query)
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是信息充分性评估助手。只输出 JSON，不要其他内容。",
            temperature=0.1,
            max_tokens=300,
            timeout=20,
        )
        js = reply.strip()
        if js.startswith("```"):
            js = re.sub(r"^```\w*\n?", "", js)
            js = re.sub(r"\n?```$", "", js)
        data = json.loads(js)
        return {
            "sufficient": bool(data.get("sufficient", False)),
            "missing_dimensions": list(data.get("missing_dimensions", [])),
            "confidence": float(data.get("confidence", 0.0)),
            "rationale": str(data.get("rationale", "LLM 返回格式异常")),
        }
    except Exception:
        return {
            "sufficient": False,
            "missing_dimensions": ["评估异常"],
            "confidence": 0.0,
            "rationale": "LLM 异常",
        }


class SetLevelSufficiency:
    """算子 2: 全量聚合后判证据充分性。"""
    name = "set_sufficiency"

    def apply(self, docs: list[IngestedDocument], query: str) -> dict:
        return assess_sufficiency(docs, query)


# ── 可信度标签映射 ──

def _label_from_relations(relations: list[dict]) -> str:
    """根据源间关系推导可信度标签。

    优先级：矛盾 > 分歧 > 一致/互补 > 孤立
    映射关系：_RELATION_TO_CREDIBILITY 为单数据源。
    """
    if not relations:
        return _RELATION_TO_CREDIBILITY["缺失"]
    has_contradiction = any(r["label"] == "矛盾" for r in relations)
    has_divergence = any(r["label"] == "分歧" for r in relations)
    all_consistent = all(r["label"] in ("一致", "互补") for r in relations)

    if has_contradiction:
        return _RELATION_TO_CREDIBILITY["矛盾"]
    if has_divergence:
        return _RELATION_TO_CREDIBILITY["分歧"]
    if all_consistent:
        # 一致和互补都映射到"高可信"
        return _RELATION_TO_CREDIBILITY["一致"]
    return _RELATION_TO_CREDIBILITY["分歧"]


# ── CredibilityFuser Step ──

class CredibilityFuserStep:
    """S4: 对摄取文档做可信度融合。v1 启用 relation + sufficiency 两个算子。"""

    def __init__(self, name: str = "S4"):
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        docs = input.previous_outputs.get("S3_fetch", {}).get("documents", [])
        return len(docs) == 0

    def run(self, input: StepInput) -> StepOutput:
        docs: list[IngestedDocument] = input.previous_outputs.get("S3_fetch", {}).get("documents", [])
        if not docs:
            return StepOutput(
                step_name=self.name,
                status="skipped",
                data={"reason": "无文档"},
                confidence=1.0,
            )

        operators: list[str] = input.config.get("operators", ["relation", "sufficiency"])
        conflicts: list[dict] = []
        sufficiency: dict = {}

        # 算子 1: 源间关系分类
        if "relation" in operators:
            classifier = SourceRelationClassifier()
            relations = classifier.apply(docs)
            conflicts = [r for r in relations if r["label"] in ("矛盾", "分歧")]

            # 根据关系调整每个文档的可信度
            for doc in docs:
                rels_for_doc = [
                    r for r in relations
                    if r.get("doc_a_id") == doc.id or r.get("doc_b_id") == doc.id
                ]
                label = _label_from_relations(rels_for_doc)
                doc.credibility_score = _CREDIBILITY_SCORES.get(label, 0.2)

                # 将标签写入 structured
                if doc.structured is None:
                    doc.structured = {}
                doc.structured["credibility_label"] = label

        # 算子 2: 集合级充分性
        if "sufficiency" in operators:
            sufficiency = assess_sufficiency(docs, input.query)

        # 检查是否需要人机协同
        needs_human = False
        human_question = None
        if conflicts and sufficiency.get("sufficient") is False:
            needs_human = True
            human_question = "多源信息存在冲突且证据不充分，是否继续基于现有信息生成方案？"

        return StepOutput(
            step_name=self.name,
            status="needs_human" if needs_human else "ok",
            data={
                "documents": docs,
                "conflicts": conflicts,
                "sufficiency": sufficiency,
            },
            human_question=human_question,
            confidence=0.7 if not conflicts else 0.4,
        )
