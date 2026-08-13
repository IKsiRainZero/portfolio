"""
安全 Python 代码执行器 — 在子进程中运行并返回测试结果
"""
import sys
import json
import subprocess


def run_tests(code, func_name, test_cases, timeout=5):
    """在沙箱子进程中执行代码并验证测试用例，返回结果列表"""
    if not code or not func_name:
        raise ValueError("代码和函数名不能为空")

    test_script = f'''
import sys
import json
import traceback

{code}

results = []
test_cases = {json.dumps(test_cases)}

for tc in test_cases:
    try:
        inp = tc["input"]
        if isinstance(inp, dict):
            actual = {func_name}(**inp)
        else:
            actual = {func_name}(inp)
        expected = tc["expected"]

        if isinstance(expected, list):
            if len(actual) != len(expected):
                passed = False
            else:
                passed = True
                for a, e in zip(actual, expected):
                    if a is None and e is None:
                        continue
                    if a is None or e is None:
                        passed = False
                        break
                    if abs(a - e) > 1e-6:
                        passed = False
                        break
        else:
            passed = abs(actual - expected) < 1e-6

        results.append({{
            "passed": passed,
            "input": str(inp),
            "expected": expected,
            "actual": actual,
            "error": None
        }})
    except Exception as e:
        results.append({{
            "passed": False,
            "input": str(tc["input"]),
            "expected": tc["expected"],
            "actual": None,
            "error": f"{{type(e).__name__}}: {{e}}"
        }})

print(json.dumps(results))
'''

    proc = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if proc.returncode != 0:
        return {
            "error": "代码执行出错",
            "stderr": proc.stderr[:500],
            "stdout": proc.stdout[:500],
        }

    try:
        results = json.loads(proc.stdout.strip())
        return {"results": results}
    except json.JSONDecodeError:
        return {
            "error": "无法解析执行结果",
            "stdout": proc.stdout[:500],
        }
