"""Harness 校验链 — 可插拔的 Agent 执行后校验规则。

新增校验规则: 继承 Validator，实现 check()，加入 VALIDATORS 列表即可。
"""
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    passed: bool
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class Validator:
    """校验器基类"""
    name: str = "base"

    def check(self, reply: str, steps: list, tool_calls: int) -> CheckResult:
        raise NotImplementedError


# ── 内置校验器 ──

class EmptyReplyValidator(Validator):
    """空回复检测: 无实际回复内容时标记"""
    name = "empty_reply"

    def check(self, reply, steps, tool_calls):
        if not reply or not reply.strip():
            return CheckResult(passed=False, issues=["Agent 未生成回复"])
        # 回复太短且有工具调用但无实质内容
        if len(reply.strip()) < 10 and tool_calls > 0:
            return CheckResult(passed=False, issues=[f"回复过短 ({len(reply)}字符)，可能未正确总结工具返回"])
        return CheckResult(passed=True)


class ToolErrorValidator(Validator):
    """工具执行错误检测: 扫描 observation 阶段的错误信息"""
    name = "tool_error"

    def check(self, reply, steps, tool_calls):
        issues = []
        for s in steps:
            if s.get("phase") != "observation":
                continue
            output = s.get("output", "")
            if any(kw in output for kw in ("失败:", "失败：", "错误:", "Error:", "超时", "未连接")):
                issues.append(f"工具 {s.get('tool', '?')} 返回异常: {output[:120]}")
        if issues:
            return CheckResult(passed=False, issues=issues)
        return CheckResult(passed=True)


class ToolCallLoopValidator(Validator):
    """工具调用循环检测: 同一工具被连续调用超过阈值时警告"""
    name = "tool_loop"
    threshold: int = 4

    def check(self, reply, steps, tool_calls):
        warnings = []
        consecutive = {}
        max_consecutive = {}
        for s in steps:
            if s.get("phase") == "action":
                name = s.get("tool", "unknown")
                consecutive[name] = consecutive.get(name, 0) + 1
                max_consecutive[name] = max(max_consecutive.get(name, 0), consecutive[name])
            else:
                consecutive.clear()
        for tool, count in max_consecutive.items():
            if count >= self.threshold:
                warnings.append(f"工具 '{tool}' 被连续调用 {count} 次，可能存在循环")
        return CheckResult(passed=True, warnings=warnings)


class SourceReferenceValidator(Validator):
    """来源完整性: search_knowledge 调用后，回复须引用至少一处来源"""
    name = "source_reference"

    def check(self, reply, steps, tool_calls):
        used_search = any(
            s.get("tool") == "search_knowledge"
            for s in steps if s.get("phase") == "action"
        )
        if not used_search:
            return CheckResult(passed=True)

        has_source = any(pat in reply for pat in (
            "arxiv", "ArXiv", "arXiv",
            ".pdf", "论文", "来源",
            "知识库", "来源:", "参考",
        ))
        if not has_source:
            return CheckResult(
                passed=False,
                issues=["search_knowledge 已调用但回复未引用任何来源，需标注知识出处"],
            )
        return CheckResult(passed=True)


class OutputStructureValidator(Validator):
    """输出格式校验: 关键 tool 调用后检查回复基本结构"""
    name = "output_structure"

    TOOL_STRUCTURE_CHECKS = {
        "generate_question": ["题目", "选项"],
        "evaluate_answer": ["正确", "得分", "评价"],
        "diagnose_weakness": ["薄弱", "建议"],
        "create_study_plan": ["计划", "阶段"],
        "analyze_progress": ["进度", "完成"],
    }

    def check(self, reply, steps, tool_calls):
        issues = []
        for s in steps:
            if s.get("phase") != "action":
                continue
            tool = s.get("tool", "")
            if tool not in self.TOOL_STRUCTURE_CHECKS:
                continue
            checks = self.TOOL_STRUCTURE_CHECKS[tool]
            missing = [k for k in checks if k not in reply]
            if len(missing) >= len(checks):  # 全部缺失才报
                issues.append(
                    f"{tool} 输出缺少基本要素: {', '.join(missing)}"
                )
        if issues:
            return CheckResult(passed=False, issues=issues)
        return CheckResult(passed=True)


# ── 校验链 ──

VALIDATORS: list[Validator] = [
    EmptyReplyValidator(),
    ToolErrorValidator(),
    ToolCallLoopValidator(),
    SourceReferenceValidator(),
    OutputStructureValidator(),
]


def run_harness(reply: str, steps: list, tool_calls: int) -> dict:
    """执行全部校验器，返回校验结果。

    Returns:
        {"passed": bool, "issues": [...], "warnings": [...], "details": [...]}
    """
    all_passed = True
    all_issues = []
    all_warnings = []
    details = []

    for v in VALIDATORS:
        try:
            r = v.check(reply, steps, tool_calls)
            if not r.passed:
                all_passed = False
                all_issues.extend(r.issues)
            all_warnings.extend(r.warnings)
            details.append({"validator": v.name, "passed": r.passed,
                          "issues": r.issues, "warnings": r.warnings})
        except Exception as e:
            details.append({"validator": v.name, "passed": False,
                          "issues": [f"校验器异常: {e}"]})
            all_passed = False

    return {
        "passed": all_passed,
        "issues": all_issues,
        "warnings": all_warnings,
        "details": details,
    }
