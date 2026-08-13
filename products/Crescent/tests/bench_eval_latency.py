"""
Command 5: /api/eval/summary latency benchmark.
President ruling: 100 requests, record p50/p95/p99. p95 must be < 500ms.
Result saved as performance baseline for all future phases.
"""
import sys
import time
import statistics
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


def main():
    print("Command 5: /api/eval/summary Latency Benchmark")
    print("=" * 60)

    rounds = 100
    config.EVAL_ENABLED = True
    config.EVAL_SHADOW_MODE = False

    from server import create_app
    app = create_app()
    client = app.test_client()

    admin_token = config.EVAL_ADMIN_SECRET
    headers = {"X-Admin-Token": admin_token}

    # Warmup
    for _ in range(10):
        client.get("/api/eval/summary", headers=headers)

    # Benchmark
    times = []
    errors = []
    for i in range(rounds):
        start = time.perf_counter()
        resp = client.get("/api/eval/summary", headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            times.append(elapsed_ms)
        else:
            errors.append((i, resp.status_code))

    if errors:
        print(f"\n  WARNING: {len(errors)} requests failed:")
        for idx, code in errors[:5]:
            print(f"    request #{idx}: HTTP {code}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")

    if not times:
        print("  FATAL: No successful requests — cannot compute percentiles")
        return

    s = sorted(times)
    p50 = statistics.median(s)
    p95 = s[int(len(s) * 0.95)]
    p99 = s[int(len(s) * 0.99)]
    mean = statistics.mean(times)
    stdev = statistics.stdev(times) if len(times) > 1 else 0
    p95_pass = p95 < 500

    print(f"\n  Rounds:     {rounds} ({len(times)} OK, {len(errors)} errors)")
    print(f"  P50:        {p50:.2f} ms")
    print(f"  P95:        {p95:.2f} ms")
    print(f"  P99:        {p99:.2f} ms")
    print(f"  Mean:       {mean:.2f} ms")
    print(f"  Stdev:      {stdev:.2f} ms")
    print(f"  Min/Max:    {min(times):.2f} / {max(times):.2f} ms")
    print(f"\n  P95 < 500ms: {'PASS' if p95_pass else 'FAIL'}")

    result = {
        "benchmark": "/api/eval/summary latency",
        "timestamp": datetime.now().isoformat(),
        "commit": _get_commit(),
        "config": {"rounds": rounds, "eval_enabled": True, "eval_shadow_mode": False},
        "results": {
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "mean_ms": round(mean, 2),
            "stdev_ms": round(stdev, 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "successful": len(times),
            "errors": len(errors),
            "p95_pass": p95_pass,
        },
    }

    report_path = Path(__file__).parent.parent / "docs" / "eval" / "bench-latency.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  Baseline saved: {report_path}")

    if not p95_pass:
        print("\n  ACTION REQUIRED: p95 exceeds 500ms — optimize before Phase 4")

    config.EVAL_ENABLED = False


def _get_commit():
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
                           cwd=str(Path(__file__).parent.parent))
        return r.stdout.strip()[:40] if r.returncode == 0 else None
    except Exception:
        return None


if __name__ == "__main__":
    main()
