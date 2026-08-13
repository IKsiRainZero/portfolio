"""diagnostics — 开发诊断工具集。

从 services/eval/ 降级而来。只保留 CI 可用的 schema 校验，
移除 LLM Judge / Meta Evaluator / Golden Dataset 的产品级暴露。
"""

from tools.diagnostics.skill_health import SkillHealthCheck, run_skill_diagnostics

__all__ = ["SkillHealthCheck", "run_skill_diagnostics"]
