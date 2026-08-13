"""
Agent vs 直接 LLM 对比评测
对比 Agent (ReAct + 9 Tools) 与直接 LLM 在 10 个任务上的表现。

用法:
  python scripts/eval_agent.py                    # 运行对比
  python scripts/eval_agent.py --output results.json
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_service import agent_chat
from services.deepseek_client import chat as direct_chat

# 10 个测试任务，覆盖不同 Agent 能力
# 每个任务标注：需要什么 tool、评判标准
TEST_CASES = [
    {
        "id": 1,
        "name": "知识检索",
        "query": "请搜索知识库，告诉我 Self-Evolution 在 AI Agent 中是什么意思？",
        "expected_tools": ["search_knowledge"],
        "check": "hit"  # 是否调用了 search_knowledge
    },
    {
        "id": 2,
        "name": "出题练习",
        "query": "请用 generate_question 工具生成一道关于 Python 列表推导式的选择题（中等难度）。",
        "expected_tools": ["generate_question"],
        "check": "hit"
    },
    {
        "id": 3,
        "name": "进度查询",
        "query": "帮我查一下我的学习进度，调用 analyze_progress。",
        "expected_tools": ["analyze_progress"],
        "check": "hit"
    },
    {
        "id": 4,
        "name": "薄弱诊断",
        "query": "调用 diagnose_weakness 诊断我的薄弱环节，然后给我学习建议。",
        "expected_tools": ["diagnose_weakness"],
        "check": "hit"
    },
    {
        "id": 5,
        "name": "费曼检查",
        "query": "请用 feynman_check 评估我对「反向传播」的解释：反向传播就是通过链式法则从输出层向输入层逐层计算梯度，用来更新神经网络的权重参数。",
        "expected_tools": ["feynman_check"],
        "check": "hit"
    },
    {
        "id": 6,
        "name": "深度提问",
        "query": "请用 deep_question 工具为「过拟合」这个概念出一道场景迁移题，我是中级水平。",
        "expected_tools": ["deep_question"],
        "check": "hit"
    },
    {
        "id": 7,
        "name": "学习计划",
        "query": "请先调用 diagnose_weakness 查看我的薄弱点，然后调用 create_study_plan 生成学习计划。",
        "expected_tools": ["diagnose_weakness", "create_study_plan"],
        "check": "multi"  # 需要调用多个工具
    },
    {
        "id": 8,
        "name": "答案评估",
        "query": "请用 evaluate_answer 工具评估这个回答：题目「什么是RAG？」回答「RAG是检索增强生成，先检索相关文档再让LLM基于文档生成答案。」",
        "expected_tools": ["evaluate_answer"],
        "check": "hit"
    },
    {
        "id": 9,
        "name": "综合任务",
        "query": "搜索知识库中关于 Transformer 的内容，然后给我出一道关于注意力机制的选择题。",
        "expected_tools": ["search_knowledge", "generate_question"],
        "check": "multi"
    },
    {
        "id": 10,
        "name": "知识搜索+诊断",
        "query": "搜索知识库中关于 Skill Learning 的内容，然后分析我的学习进度，最后给我一个学习计划。",
        "expected_tools": ["search_knowledge", "analyze_progress", "create_study_plan"],
        "check": "multi"
    }
]


def evaluate_agent(query, session_id="eval_agent"):
    """通过 Agent 执行查询，返回 steps + reply"""
    t0 = time.time()
    try:
        result = agent_chat(query, session_id)
        elapsed = time.time() - t0
        return {
            "reply": result["reply"][:500],
            "tool_calls": result["tool_calls"],
            "tools_used": list(set(s.get("tool", "") for s in result["steps"] if s["phase"] == "action")),
            "steps": len(result["steps"]),
            "elapsed_ms": round(elapsed * 1000),
            "error": None,
        }
    except Exception as e:
        return {
            "reply": "",
            "tool_calls": 0,
            "tools_used": [],
            "steps": 0,
            "elapsed_ms": 0,
            "error": str(e),
        }


def evaluate_direct(query):
    """通过直接 LLM (无工具) 执行查询"""
    t0 = time.time()
    try:
        reply, usage = direct_chat(
            messages=[{"role": "user", "content": query}],
            system_prompt="你是一个智能学习助手。请直接回答用户的问题。",
            max_tokens=800,
        )
        elapsed = time.time() - t0
        return {
            "reply": reply[:500],
            "elapsed_ms": round(elapsed * 1000),
            "usage": usage,
            "error": None,
        }
    except Exception as e:
        return {
            "reply": "",
            "elapsed_ms": 0,
            "usage": {},
            "error": str(e),
        }


def check_result(test_case, agent_result):
    """判断 Agent 是否完成了预期任务"""
    tools_used = agent_result["tools_used"]
    expected = test_case["expected_tools"]
    check_type = test_case["check"]

    if check_type == "hit":
        return any(t in tools_used for t in expected)
    elif check_type == "multi":
        return all(t in tools_used for t in expected)

    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent vs Direct LLM 对比评测")
    parser.add_argument("--output", type=str, help="输出 JSON 文件路径")
    parser.add_argument("--skip-direct", action="store_true", help="跳过高成本的直接 LLM 对比")
    args = parser.parse_args()

    print(f"Agent vs Direct LLM 对比评测 — {len(TEST_CASES)} 个任务\n")
    print(f"{'='*70}")

    results = []
    agent_success = 0
    agent_total_tools = 0
    agent_total_time = 0
    direct_total_time = 0

    for tc in TEST_CASES:
        print(f"\n[{tc['id']:2d}] {tc['name']}")
        print(f"    预期工具: {tc['expected_tools']}")

        # Agent 评测
        agent_r = evaluate_agent(tc["query"], session_id=f"eval_{tc['id']}")
        success = check_result(tc, agent_r)
        if success:
            agent_success += 1
        agent_total_tools += agent_r["tool_calls"]
        agent_total_time += agent_r["elapsed_ms"]

        status = "OK" if success else "FAIL"
        print(f"    Agent: {status} | tools={agent_r['tools_used']} | {agent_r['elapsed_ms']}ms | {agent_r['tool_calls']} tool calls")

        if agent_r["error"]:
            print(f"    Agent ERR: {agent_r['error']}")

        # Direct LLM 评测
        direct_r = {"reply": "", "elapsed_ms": 0, "usage": {}, "error": "skipped"}
        if not args.skip_direct:
            direct_r = evaluate_direct(tc["query"])
            direct_total_time += direct_r["elapsed_ms"]
            print(f"    Direct: {direct_r['elapsed_ms']}ms | reply={direct_r['reply'][:80]}...")
            if direct_r["error"]:
                print(f"    Direct ERR: {direct_r['error']}")

        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "expected_tools": tc["expected_tools"],
            "agent": {
                "success": success,
                "tools_used": agent_r["tools_used"],
                "tool_calls": agent_r["tool_calls"],
                "elapsed_ms": agent_r["elapsed_ms"],
                "reply_preview": agent_r["reply"][:150],
            },
            "direct": {
                "elapsed_ms": direct_r["elapsed_ms"],
                "reply_preview": direct_r["reply"][:150],
            },
        })

    # 汇总
    n = len(TEST_CASES)
    print(f"\n{'='*70}")
    print(f"  对比汇总")
    print(f"{'='*70}")
    print(f"  Agent 任务完成率:     {agent_success}/{n} ({agent_success/n:.0%})")
    print(f"  Agent 总 Tool 调用:   {agent_total_tools}")
    print(f"  Agent 平均耗时:       {agent_total_time/n:.0f}ms")
    if not args.skip_direct:
        print(f"  Direct LLM 平均耗时:  {direct_total_time/n:.0f}ms")
        print(f"  耗时比 (Agent/Direct): {agent_total_time/direct_total_time:.1f}x" if direct_total_time > 0 else "  N/A")
    print(f"  Agent 独有能力: 知识检索、出题、进度诊断、费曼检查、深度提问、学习计划生成")
    print(f"  Direct LLM 能力: 只有通用问答，无工具调用，无记忆持久化")

    summary = {
        "total_cases": n,
        "agent_success_rate": round(agent_success / n, 4),
        "agent_total_tool_calls": agent_total_tools,
        "agent_avg_latency_ms": round(agent_total_time / n, 1),
        "direct_avg_latency_ms": round(direct_total_time / n, 1) if not args.skip_direct else 0,
    }

    output = {"summary": summary, "details": results}

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入: {args.output}")

    return output


if __name__ == "__main__":
    main()
