import json
import re
import subprocess
import tempfile
from pathlib import Path

from mayihelpu.context import ProblemContext, SolveResult
from mayihelpu.llm import LLMClient, get_default_client
from mayihelpu.sandbox import Sandbox


SOLVE_SYSTEM = """You are an execution planner. Given solutions with their resources, produce a concrete, ordered execution plan.

Rules:
1. Each step must be a concrete action: install a package, create a file, run a command, write a function
2. Steps are ordered by dependency: foundation first (project setup, installs), then implementation, then testing
3. command is the exact shell command or pseudocode to execute
4. expected_output describes what success looks like for this step
5. Output a JSON object with key "steps" — an ordered array of step objects, each with:
   - id: string (kebab-case, numbered)
   - action: string (what to do, 1 sentence)
   - command: string (exact command or pseudocode)
   - expected_output: string (what to verify after)
   - depends_on: list of step ids that must complete first

Output ONLY the JSON object, no markdown, no explanation."""

EXECUTE_SYSTEM = """You are an execution agent. Execute a step by calling available tools.

Rules:
1. Choose the right tool for the step's action
2. Call run_shell with cwd={workspace} for all commands
3. Call file_write with path relative to {workspace}
4. If no tool fits, use the skip action"""


def _builtin_run_shell(command: str, cwd: str = "") -> dict:
    """Execute a shell command and return stdout, stderr, and return code."""
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=60, cwd=cwd or None,
        )
        return {"stdout": r.stdout[:2000], "stderr": r.stderr[:2000], "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout after 60s", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def _builtin_file_write(path: str, content: str) -> dict:
    """Write content to a file, creating parent directories as needed."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "size": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


BUILTIN_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command and return stdout, stderr, and return code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                    "cwd": {"type": "string", "description": "Optional working directory."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file, creating parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to."},
                    "content": {"type": "string", "description": "Content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "run_shell": _builtin_run_shell,
    "file_write": _builtin_file_write,
}


class Solver:
    def __init__(self, llm: LLMClient | None = None, workspace: str = "", dry_run: bool = False):
        self.llm = llm or get_default_client()
        self.workspace = workspace or str(Path(tempfile.gettempdir()) / "mayihelpu-workspace")
        self.sandbox = Sandbox(self.workspace, dry_run=dry_run)
        self.tool_registry: dict[str, dict] = {}
        for tool in BUILTIN_TOOLS:
            name = tool["function"]["name"]
            self.tool_registry[name] = {
                "func": TOOL_FUNCTIONS[name],
                "schema": tool,
            }

    def register_tool(self, name: str, func: callable, description: str, parameters: dict):
        self.tool_registry[name] = {
            "func": func,
            "schema": {
                "type": "function",
                "function": {"name": name, "description": description, "parameters": parameters},
            },
        }

    def solve(self, ctx: ProblemContext) -> ProblemContext:
        ctx.log("Solver", f"solve solutions={len(ctx.solutions)} resources={len(ctx.resources)}", "")
        if not ctx.solutions:
            ctx.result = SolveResult(success=False, output="No solutions to execute")
            return ctx

        if not ctx.result.steps:
            self._plan(ctx)

        results = self._execute(ctx)
        ctx.result = SolveResult(
            success=all(r.get("ok", True) for r in results),
            output=f"Executed {len(results)} steps",
            steps=ctx.result.steps,
        )
        ctx.log("Solver", "done", f"{len(results)} steps executed")
        return ctx

    # ── plan ──

    def _plan(self, ctx: ProblemContext):
        sol_text = "\n".join(
            f"[{s.id}] {s.method} (feasibility={s.feasibility})" for s in ctx.solutions
        )
        res_text = "\n".join(
            f"[{r.id}] {r.url} — {r.summary}" for r in ctx.resources
        )
        user_prompt = (
            f"Solutions:\n{sol_text}\n\nAvailable resources:\n{res_text}\n\n"
            f"Produce an ordered execution plan."
        )
        response = self.llm.chat(system=SOLVE_SYSTEM, user=user_prompt, temperature=0.2)
        data = self._parse(response)
        ctx.result.steps = self._format_steps(data.get("steps", []) if isinstance(data, dict) else [])

    def _format_steps(self, raw_steps: list[dict]) -> list[str]:
        formatted: list[str] = []
        for s in raw_steps:
            deps = s.get("depends_on", [])
            dep_str = f" (after: {', '.join(deps)})" if deps else ""
            line = f"[{s.get('id', '?')}] {s.get('action', '')}{dep_str}\n"
            line += f"  $ {s.get('command', '')}\n"
            line += f"  -> {s.get('expected_output', '')}"
            formatted.append(line)
        return formatted

    # ── execute ──

    def _execute(self, ctx: ProblemContext) -> list[dict]:
        Path(self.workspace).mkdir(parents=True, exist_ok=True)
        tools = [t["schema"] for t in self.tool_registry.values()]
        results: list[dict] = []
        ws = self.workspace

        for step_text in ctx.result.steps:
            result = {"step": step_text[:80], "ok": False}
            try:
                resp = self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    temperature=0.1,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": EXECUTE_SYSTEM.format(workspace=ws)},
                        {"role": "user", "content": f"Execute this step:\n{step_text}"},
                    ],
                    tools=tools,
                    tool_choice="auto",
                )
                msg = resp.choices[0].message
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        name = tc.function.name
                        args = json.loads(tc.function.arguments)
                        if name in self.tool_registry:
                            if name == "run_shell":
                                cmd = args.get("command", "")
                                allowed, reason = self.sandbox.check(cmd)
                                if not allowed:
                                    result["ok"] = False
                                    result["error"] = f"Sandbox blocked: {reason}"
                                    continue
                                if self.sandbox.dry_run:
                                    result["ok"] = True
                                    result["dry_run"] = True
                                    result["preview"] = self.sandbox.preview(cmd)
                                    continue
                                if "cwd" not in args:
                                    args["cwd"] = ws
                            if name == "file_write":
                                if not Path(args["path"]).is_absolute():
                                    args["path"] = str(Path(ws) / args["path"])
                            exec_result = self.tool_registry[name]["func"](**args)
                            result.update(exec_result)
                            result["ok"] = exec_result.get("ok", exec_result.get("returncode", 1) == 0)
                elif msg.content:
                    # LLM responded with text instead of tool call — treat as skip
                    result["ok"] = True
                    result["skipped"] = True
                    result["reason"] = msg.content[:200]
            except Exception as e:
                result["error"] = str(e)
            results.append(result)

        return results

    # ── helpers ──

    def _parse(self, response: str) -> dict | list:
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*", "", response)
            response = re.sub(r"\s*```$", "", response)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {}
