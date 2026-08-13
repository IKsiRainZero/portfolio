"""Baseline audit: 20 manually constructed doc pairs covering all 5 relation labels.

每个 pair 有 doc_a、doc_b 和 expected label。
通过 classify_relation() 运行并计算准确率。
准确率 < 75% 时应调整 few-shot 示例并重新运行。
"""
from __future__ import annotations
from services.pipeline.credibility import classify_relation, RELATION_LABELS
from services.pipeline.types import IngestedDocument


# ── 测试数据：20 个手动标注 pair ──

BASELINE_PAIRS: list[dict] = [
    # ── 一致 (5 pairs): 相同主张，不同措辞 ──
    {
        "doc_a": "Transformer使用自注意力机制并行处理序列",
        "doc_b": "The Transformer relies on self-attention for parallel processing",
        "expected": "一致",
    },
    {
        "doc_a": "BERT在GLUE基准上达到SOTA",
        "doc_b": "BERT achieved state-of-the-art on the GLUE benchmark",
        "expected": "一致",
    },
    {
        "doc_a": "数据增强可提升模型泛化能力",
        "doc_b": "Data augmentation improves model generalization performance",
        "expected": "一致",
    },
    {
        "doc_a": "残差连接解决了深层网络的梯度消失问题",
        "doc_b": "Residual connections address the vanishing gradient problem in deep networks",
        "expected": "一致",
    },
    {
        "doc_a": "学习率预热策略可以稳定训练初期的梯度更新",
        "doc_b": "Learning rate warmup stabilizes gradient updates in early training stages",
        "expected": "一致",
    },
    # ── 互补 (4 pairs): 同一大领域的不同子话题，合起来更全面 ──
    {
        "doc_a": "CNN使用卷积核提取图像的局部特征",
        "doc_b": "池化层降低特征图尺寸，减少参数量并防止过拟合",
        "expected": "互补",
    },
    {
        "doc_a": "随机梯度下降SGD是最常用的优化器之一",
        "doc_b": "Adam优化器结合动量和自适应学习率，收敛更快",
        "expected": "互补",
    },
    {
        "doc_a": "ResNet通过残差连接训练超过百层的深度网络",
        "doc_b": "DenseNet通过密集连接实现特征复用，减少参数量",
        "expected": "互补",
    },
    {
        "doc_a": "Dropout在训练时随机丢弃神经元防止过拟合",
        "doc_b": "Batch Normalization通过归一化层输入加速训练收敛",
        "expected": "互补",
    },
    # ── 分歧 (4 pairs): 同一狭窄主题的不同细节，信息不同但不冲突 ──
    {
        "doc_a": "BERT在GLUE基准上达到SOTA，超过人类水平",
        "doc_b": "BERT在GLUE上的结果被后续研究发现存在评估漏洞",
        "expected": "分歧",
    },
    {
        "doc_a": "Transformer的注意力头数通常设为8或16",
        "doc_b": "不同任务中最优注意力头数差异很大，没有统一标准",
        "expected": "分歧",
    },
    {
        "doc_a": "ResNet-50在ImageNet上的Top-1准确率为76.1%",
        "doc_b": "ResNet-50的Top-5准确率达到92.9%，说明预测前5名基本正确",
        "expected": "分歧",
    },
    {
        "doc_a": "BERT使用BooksCorpus和英文维基百科进行预训练",
        "doc_b": "BERT的预训练语料包含约33亿个token，数据量庞大",
        "expected": "分歧",
    },
    # ── 矛盾 (4 pairs): 就同一具体事实给出直接对立的主张 ──
    {
        "doc_a": "学习率设置为0.01时模型收敛最快且效果最好",
        "doc_b": "实验表明0.001的学习率收敛效果最好，0.01会导致训练发散",
        "expected": "矛盾",
    },
    {
        "doc_a": "L2正则化对防止过拟合无效，应该优先使用Dropout",
        "doc_b": "L2正则化是防止过拟合最有效的方法，不能轻易替代",
        "expected": "矛盾",
    },
    {
        "doc_a": "深度可分离卷积参数量远少于普通卷积且性能相近",
        "doc_b": "深度可分离卷积的性能远不如普通卷积，参数量优势无实际意义",
        "expected": "矛盾",
    },
    {
        "doc_a": "增大Batch Size可以显著提升训练速度且不影响最终精度",
        "doc_b": "增大Batch Size会导致模型收敛到尖锐极值点，泛化性能显著下降",
        "expected": "矛盾",
    },
    # ── 缺失 (3 pairs): 主题完全不同，没有交集 ──
    {
        "doc_a": "Transformer使用自注意力机制并行处理序列",
        "doc_b": "CNN通过卷积核提取图像的边缘和纹理特征",
        "expected": "缺失",
    },
    {
        "doc_a": "BERT使用掩码语言模型进行预训练",
        "doc_b": "数据增强技术包括随机裁剪、旋转等图像变换",
        "expected": "缺失",
    },
    {
        "doc_a": "Adam优化器结合动量和自适应学习率，适合非平稳目标",
        "doc_b": "巴黎是法国的首都，以埃菲尔铁塔和卢浮宫闻名",
        "expected": "缺失",
    },
]


def _make_doc(id: str, text: str) -> IngestedDocument:
    return IngestedDocument(
        id=id,
        text=text,
        source_url=f"http://{id}.com",
        source_type="webpage",
        credibility_score=0.5,
        tags=[],
    )


# ── 确保测试数据分布合理 ──


def test_baseline_label_coverage():
    """验证 20 个 pair 覆盖全部 5 个标签，每个 ≥3 个。"""
    counts: dict[str, int] = {}
    for pair in BASELINE_PAIRS:
        label = pair["expected"]
        counts[label] = counts.get(label, 0) + 1

    for label in RELATION_LABELS:
        assert counts.get(label, 0) >= 3, (
            f"Label '{label}' 只有 {counts.get(label, 0)} 个 pair，需要 ≥3"
        )

    total = sum(counts.values())
    assert total == 20, f"总共 {total} 个 pair，预期 20"


# ── 基线审计：通过真实 LLM 调用评估准确率 ──


def test_baseline_accuracy():
    """对 20 个 pair 逐个调用 classify_relation()，计算总体准确率。

    如果准确率 < 75%，需要调整 few-shot 示例后重新运行。
    """
    correct = 0
    total = len(BASELINE_PAIRS)
    errors: list[dict] = []

    for i, pair in enumerate(BASELINE_PAIRS):
        doc_a = _make_doc(f"a_{i}", pair["doc_a"])
        doc_b = _make_doc(f"b_{i}", pair["doc_b"])
        result = classify_relation(doc_a, doc_b)
        predicted = result["label"]
        expected = pair["expected"]
        if predicted == expected:
            correct += 1
        else:
            errors.append({
                "index": i,
                "doc_a": pair["doc_a"][:60],
                "doc_b": pair["doc_b"][:60],
                "expected": expected,
                "predicted": predicted,
                "confidence": result.get("confidence", 0),
                "rationale": result.get("rationale", ""),
            })

    accuracy = correct / total
    summary = (
        f"\n{'='*60}\n"
        f"基线审计结果\n"
        f"总 pair 数: {total}\n"
        f"正确: {correct}\n"
        f"错误: {total - correct}\n"
        f"准确率: {accuracy:.1%}\n"
        f"目标: ≥75%\n"
        f"{'='*60}\n"
    )

    if errors:
        summary += "\n错误详情:\n"
        for e in errors:
            summary += (
                f"  #{e['index']}: expected={e['expected']} "
                f"predicted={e['predicted']} "
                f"(conf={e['confidence']:.2f}) "
                f"\"{e['rationale'][:60]}\"\n"
                f"    doc_a: {e['doc_a']}\n"
                f"    doc_b: {e['doc_b']}\n"
            )
        summary += f"\n{'='*60}\n"

    # 将详细结果打印到 stdout（pytest -v 会展示）
    print(summary)

    assert accuracy >= 0.75, (
        f"基线准确率 {accuracy:.1%} < 75%，需要调整 few-shot 示例"
    )
