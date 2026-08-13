from __future__ import annotations
from dataclasses import dataclass, field

from services.workbench.types import Profile
from services.workbench.gap_analyzer import GapReport, GapItem


@dataclass
class Module:
    title: str
    description: str
    estimated_hours: float
    resource_type: str   # "tutorial" | "course" | "book" | "project"


@dataclass
class Phase:
    name: str
    duration: str
    difficulty: str         # "beginner" | "intermediate" | "advanced"
    prerequisites: list[str] = field(default_factory=list)
    modules: list[Module] = field(default_factory=list)


@dataclass
class LearningPath:
    phases: list[Phase] = field(default_factory=list)


_RESOURCE_TEMPLATES = {
    "python": Module("Python 进阶", "系统学习 Python 高级特性、异步编程、类型系统",
                      40, "course"),
    "llm": Module("LLM 基础理论", "Transformer架构、预训练、微调、提示工程",
                  30, "course"),
    "langchain": Module("LangChain 实战", "构建 LLM 应用：Chain、Agent、Tool",
                         20, "tutorial"),
    "rag": Module("RAG 检索增强生成", "向量数据库、Embedding、检索策略",
                  15, "tutorial"),
    "ml": Module("机器学习基础", "监督/无监督学习、特征工程、模型评估",
                 40, "course"),
    "docker": Module("Docker 容器化", "Dockerfile、Compose、镜像优化",
                     10, "tutorial"),
    "kubernetes": Module("Kubernetes 基础", "Pod、Service、Deployment、Helm",
                          25, "course"),
    "sql": Module("SQL 进阶", "复杂查询、索引优化、事务隔离",
                  15, "tutorial"),
    "pytorch": Module("PyTorch 深度学习", "张量操作、自动求导、模型训练",
                      30, "course"),
    "aws": Module("AWS 云服务基础", "EC2、S3、Lambda、IAM",
                  20, "course"),
}


class LearningPathGenerator:
    def generate(self, gap_report: GapReport, profile: Profile) -> LearningPath:
        must_gaps = [g for g in gap_report.gaps if g.priority == "must"]
        rec_gaps = [g for g in gap_report.gaps if g.priority == "recommended"]
        opt_gaps = [g for g in gap_report.gaps if g.priority == "optional"]

        phases: list[Phase] = []

        if must_gaps:
            modules = self._gaps_to_modules(must_gaps)
            total_hours = sum(m.estimated_hours for m in modules)
            phases.append(Phase(
                name="Phase 1: 核心基础",
                duration=f"约 {max(total_hours / 10, 1):.0f}–{max(total_hours / 5, 2):.0f} 周",
                difficulty="beginner",
                prerequisites=[],
                modules=modules,
            ))

        if rec_gaps:
            modules = self._gaps_to_modules(rec_gaps)
            total_hours = sum(m.estimated_hours for m in modules)
            phases.append(Phase(
                name="Phase 2: 技能深化",
                duration=f"约 {max(total_hours / 10, 1):.0f}–{max(total_hours / 5, 2):.0f} 周",
                difficulty="intermediate",
                prerequisites=[phases[-1].name] if phases else [],
                modules=modules,
            ))

        if opt_gaps:
            modules = self._gaps_to_modules(opt_gaps)
            total_hours = sum(m.estimated_hours for m in modules)
            phases.append(Phase(
                name="Phase 3: 工具链补充",
                duration=f"约 {max(total_hours / 10, 1):.0f}–{max(total_hours / 5, 2):.0f} 周",
                difficulty="advanced",
                prerequisites=[phases[-1].name] if phases else [],
                modules=modules,
            ))

        if not phases:
            phases.append(Phase(
                name="Phase 1: 基础巩固",
                duration="约 2–4 周",
                difficulty="beginner",
                modules=[Module("基础知识回顾", "巩固现有技能，为后续学习做准备",
                                20, "tutorial")],
            ))

        return LearningPath(phases=phases)

    def _gaps_to_modules(self, gaps: list[GapItem]) -> list[Module]:
        modules: list[Module] = []
        for g in gaps:
            key = g.skill_name.lower()
            if key in _RESOURCE_TEMPLATES:
                modules.append(_RESOURCE_TEMPLATES[key])
            else:
                modules.append(Module(
                    title=f"学习 {g.skill_name}",
                    description=f"掌握 {g.skill_name} 的{g.required_level}水平",
                    estimated_hours=15,
                    resource_type="tutorial",
                ))
        return modules
