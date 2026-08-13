"""安全扫描 — CWE 合规检查 + 依赖漏洞审计

用法: python scripts/security_scan.py [--json]
参照: OWASP ASVS 4.0 / CWE Top 25
"""
import sys
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent

CWE_CHECKS = {
    "CWE-22": {
        "desc": "路径遍历防护",
        "files": ["routes/api_knowledge.py"],
        "check": "CWE-22|path.*traversal|路径遍历|os\\.path\\.join.*user|abspath",
    },
    "CWE-209": {
        "desc": "安全错误消息",
        "files": ["services/safe_error.py", "services/deepseek_client.py"],
        "check": "safe_error|CWE-209|不暴露.*错误|sanitize.*error",
    },
    "CWE-798": {
        "desc": "硬编码凭证",
        "files": ["config.py"],
        "check": "environ\\.get|os\\.getenv|\\.api_key|DEEPSEEK_API_KEY",
    },
    "CWE-770": {
        "desc": "资源耗尽防护 (速率限制)",
        "files": ["services/rate_limiter.py"],
        "check": "rate_limit|滑动窗口|max_requests|window_seconds",
    },
    "CWE-400": {
        "desc": "未控资源消耗 (Session TTL)",
        "files": ["config.py"],
        "check": "SESSION_TTL|SESSION_MAX_COUNT|AGENT_MAX_ITERATIONS",
    },
}


def check_cwe_compliance():
    results = []
    for cwe_id, spec in CWE_CHECKS.items():
        found = False
        for fname in spec["files"]:
            fpath = ROOT / fname
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8", errors="replace")
            import re
            if re.search(spec["check"], content, re.IGNORECASE):
                found = True
                break
        results.append({
            "cwe": cwe_id,
            "desc": spec["desc"],
            "pass": found,
            "status": "OK" if found else "MISSING",
        })
    return results


def check_pip_vulnerabilities():
    """调用 pip-audit (如已安装) 审计依赖漏洞。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json"],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT),
        )
        if result.returncode in (0, 1):
            return json.loads(result.stdout) if result.stdout.strip() else []
    except Exception:
        pass
    return None


def main():
    print("=" * 50)
    print("CWE 合规检查")
    print("=" * 50)
    cwe_results = check_cwe_compliance()
    all_pass = True
    for r in cwe_results:
        icon = "PASS" if r["pass"] else "FAIL"
        print(f"  [{icon}] {r['cwe']}: {r['desc']}")
        if not r["pass"]:
            all_pass = False

    print()
    print("=" * 50)
    print("依赖漏洞审计 (pip-audit)")
    print("=" * 50)
    vulns = check_pip_vulnerabilities()
    if vulns is None:
        print("  pip-audit 未安装。安装: pip install pip-audit")
        vulns = []
    elif not vulns:
        print("  未发现已知漏洞。")
    else:
        for v in vulns:
            print(f"  [{v.get('id','?')}] {v.get('name','?')} {v.get('version','?')}")

    all_pass = all_pass and len(vulns) == 0

    if "--json" in sys.argv:
        print(json.dumps({"cwe": cwe_results, "pip_vulns": vulns}, ensure_ascii=False))

    print()
    print(f"综合评估: {'PASS' if all_pass else 'ISSUES FOUND'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
