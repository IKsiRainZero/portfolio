from __future__ import annotations
from dataclasses import dataclass, field

from services.workbench.learning_path import LearningPath, Module


@dataclass
class ActionItem:
    title: str
    description: str
    estimated_time: str
    completion_criteria: str
    resource_url: str | None = None
    resource_type: str = "tutorial"  # "tutorial" | "course" | "paper" | "project" | "book"


_ACTION_TEMPLATES = {
    "python": ActionItem(
        "Python 官方教程", "完成 python.org 官方教程的主要章节",
        "约 3 小时", "能独立写出带类型标注的异步 Python 程序",
        "https://docs.python.org/3/tutorial/", "tutorial",
    ),
    "llm": ActionItem(
        "Attention Is All You Need 论文精读",
        "精读 Transformer 原始论文，理解注意力机制",
        "约 2 小时", "能用自己的话解释 Self-Attention 和 Multi-Head Attention",
        "https://arxiv.org/abs/1706.03762", "paper",
    ),
    "langchain": ActionItem(
        "LangChain 快速入门", "完成 LangChain 官方 Quickstart",
        "约 2 小时", "能独立用 LangChain 调用 GPT 模型完成一次对话",
        "https://python.langchain.com/docs/get_started/quickstart", "tutorial",
    ),
    "rag": ActionItem(
        "RAG 从零实现", "用 Chroma + OpenAI 实现一个简单的 RAG 系统",
        "约 4 小时", "能对 PDF 文档进行问答检索",
        None, "project",
    ),
    "docker": ActionItem(
        "Docker 入门教程", "完成 Docker 官方 Get Started 指南",
        "约 2 小时", "能编写 Dockerfile 并用 docker-compose 编排多容器应用",
        "https://docs.docker.com/get-started/", "tutorial",
    ),
    "sql": ActionItem(
        "SQL 进阶练习", "在 LeetCode 完成 10 道 Medium SQL 题",
        "约 3 小时", "掌握窗口函数、CTE、子查询优化",
        "https://leetcode.com/problemset/database/", "tutorial",
    ),
    "kubernetes": ActionItem(
        "Kubernetes 基础教程", "完成官方 Kubernetes Basics 教程",
        "约 3 小时", "能部署一个多副本应用到 Minikube 集群",
        "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "tutorial",
    ),
    "ml": ActionItem(
        "吴恩达机器学习课程", "完成 Coursera 机器学习前 3 周内容",
        "约 6 小时", "理解线性回归、逻辑回归、梯度下降的数学原理",
        "https://www.coursera.org/learn/machine-learning", "course",
    ),
    "pytorch": ActionItem(
        "PyTorch 60分钟入门", "完成 PyTorch 官方 60-min blitz 教程",
        "约 2 小时", "能定义神经网络、计算损失、反向传播",
        "https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html", "tutorial",
    ),
}


class NextActionGenerator:
    def generate(self, path: LearningPath, current_phase: str) -> list[ActionItem]:
        phase = None
        for p in path.phases:
            if p.name == current_phase:
                phase = p
                break
        if not phase and path.phases:
            phase = path.phases[0]

        if not phase or not phase.modules:
            return [ActionItem(
                "设定学习目标", "明确你想达成的具体职业方向和技能目标",
                "约 1 小时", "产出 3-5 个具体的、可验证的学习目标",
                resource_type="tutorial",
            )]

        actions: list[ActionItem] = []
        for mod in phase.modules[:3]:
            key = mod.title.lower()
            found = False
            for kw, template in _ACTION_TEMPLATES.items():
                if kw in key:
                    actions.append(template)
                    found = True
                    break
            if not found:
                actions.append(ActionItem(
                    title=f"开始学习: {mod.title}",
                    description=mod.description,
                    estimated_time=f"约 {mod.estimated_hours:.0f} 小时",
                    completion_criteria=f"能独立完成 {mod.title} 的核心练习",
                    resource_type=mod.resource_type,
                ))

        return actions
