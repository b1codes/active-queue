#!/usr/bin/env python3
"""Render a k6 --summary-export file as a Markdown table (for $GITHUB_STEP_SUMMARY).

python3 loadtest/summary.py loadtest/out/summary.json "Load test (local)"
"""

# ruff: noqa: T201 - a CLI

from __future__ import annotations

import json
import sys


def main() -> int:
    path, title = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Load test"
    with open(path) as f:
        metrics = json.load(f)["metrics"]
    print(f"### {title}\n")
    print("| Endpoint | p50 | p95 | p99 | Budget (p95) | |")
    print("|---|---:|---:|---:|---:|---|")
    for key in sorted(k for k in metrics if k.startswith("http_req_duration{scenario:journey")):
        m = metrics[key]
        name = key.split("name:")[-1].rstrip("}")
        budget, ok = next(iter(m.get("thresholds", {}).items()), ("", True))
        mark = "" if not budget else ("✅" if not ok else "❌")
        print(
            f"| {name} | {m['p(50)']:.0f} ms | {m['p(95)']:.0f} ms | {m['p(99)']:.0f} ms "
            f"| {budget.replace('p(95)<', '') + ' ms' if budget else ''} | {mark} |"
        )
    print("\n| Check | Value | |\n|---|---:|---|")
    for name in (
        "legit_rate_limited",
        "server_errors",
        "abuser_limited",
        "abuser_limited_without_retry_after",
        "flood_limited",
        "http_reqs",
    ):
        if name in metrics:
            m = metrics[name]
            failed = any(m.get("thresholds", {}).values())
            print(f"| {name} | {m.get('count', 0)} | {'❌' if failed else '✅'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
