#!/usr/bin/env python3
"""Compare deterministic Java/Python REST performance without model calls."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from contextlib import suppress
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))
    return ordered[index]


async def request_once(
    client: Any,
    url: str,
    semaphore: asyncio.Semaphore,
    http_error: type[Exception],
) -> dict[str, Any]:
    async with semaphore:
        started = time.perf_counter_ns()
        try:
            response = await client.get(url)
            body = response.json()
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            if response.status_code != 200 or body.get("code") != 200:
                return {
                    "elapsedMs": round(elapsed_ms, 3),
                    "error": (f"HTTP {response.status_code}, business code {body.get('code')}"),
                }
            canonical_body = json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            return {
                "bodyHash": hashlib.sha256(canonical_body).hexdigest(),
                "elapsedMs": round(elapsed_ms, 3),
            }
        except (http_error, ValueError) as error:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            return {
                "elapsedMs": round(elapsed_ms, 3),
                "error": f"{type(error).__name__}: {error}",
            }


async def run_round(
    client: Any,
    url: str,
    concurrency: int,
    requests: int,
    http_error: type[Exception],
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(concurrency)
    started = time.perf_counter_ns()
    results = await asyncio.gather(
        *(
            request_once(
                client,
                url,
                semaphore,
                http_error,
            )
            for _ in range(requests)
        )
    )
    wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    return {
        "results": results,
        "throughputRps": round(requests / (wall_ms / 1000), 3),
        "wallMs": round(wall_ms, 3),
    }


def summarize(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    results = [result for round_result in rounds for result in round_result["results"]]
    successes = [result for result in results if "error" not in result]
    errors = [result for result in results if "error" in result]
    if not successes:
        raise RuntimeError("REST performance scenario had no successful requests")
    latency_values = [float(result["elapsedMs"]) for result in successes]
    body_hashes = {str(result["bodyHash"]) for result in successes}
    round_summaries: list[dict[str, Any]] = []
    for round_result in rounds:
        round_successes = [result for result in round_result["results"] if "error" not in result]
        if not round_successes:
            raise RuntimeError("REST performance round had no successful requests")
        round_latencies = [float(result["elapsedMs"]) for result in round_successes]
        round_summaries.append(
            {
                "errorCount": len(round_result["results"]) - len(round_successes),
                "p95Ms": round(percentile(round_latencies, 0.95), 3),
                "p99Ms": round(percentile(round_latencies, 0.99), 3),
                "throughputRps": round_result["throughputRps"],
                "wallMs": round_result["wallMs"],
            }
        )
    p95_values = [float(item["p95Ms"]) for item in round_summaries]
    p99_values = [float(item["p99Ms"]) for item in round_summaries]
    throughputs = [float(item["throughputRps"]) for item in round_summaries]
    return {
        "errorCount": len(errors),
        "errorRate": round(len(errors) / len(results), 6),
        "errors": errors[:10],
        "latency": {
            "medianMs": round(statistics.median(latency_values), 3),
            "p95Ms": round(statistics.median(p95_values), 3),
            "p95RangeMs": [round(min(p95_values), 3), round(max(p95_values), 3)],
            "p99Ms": round(statistics.median(p99_values), 3),
            "p99RangeMs": [round(min(p99_values), 3), round(max(p99_values), 3)],
            "samplesMs": latency_values,
        },
        "requestCount": len(results),
        "responseHash": (next(iter(body_hashes)) if len(body_hashes) == 1 else None),
        "responseVariants": len(body_hashes),
        "rounds": round_summaries,
        "throughputMedianRps": round(statistics.median(throughputs), 3),
    }


def compare_scenario(java: dict[str, Any], python: dict[str, Any]) -> dict[str, Any]:
    java_p95 = float(java["latency"]["p95Ms"])
    java_p99 = float(java["latency"]["p99Ms"])
    python_p95 = float(python["latency"]["p95Ms"])
    python_p99 = float(python["latency"]["p99Ms"])
    p95_allowed = min(java_p95 * 1.10, java_p95 + 100)
    p99_allowed = java_p99 * 1.15
    throughput_minimum = float(java["throughputMedianRps"]) * 0.90
    return {
        "criteria": {
            "p95AllowedMs": round(p95_allowed, 3),
            "p99AllowedMs": round(p99_allowed, 3),
            "throughputMinimumRps": round(throughput_minimum, 3),
        },
        "java": java,
        "passed": (
            python_p95 <= p95_allowed
            and python_p99 <= p99_allowed
            and float(python["throughputMedianRps"]) >= throughput_minimum
            and int(python["errorCount"]) <= int(java["errorCount"])
            and java["responseVariants"] == 1
            and python["responseVariants"] == 1
            and java["responseHash"] == python["responseHash"]
        ),
        "python": python,
    }


def process_tree_pids(root_pid: int) -> set[int]:
    parent_by_pid: dict[int, int] = {}
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            lines = status_path.read_text(encoding="ascii").splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        parent_line = next(
            (line for line in lines if line.startswith("PPid:")),
            None,
        )
        if parent_line is None:
            continue
        parent_by_pid[int(status_path.parent.name)] = int(parent_line.split()[1])

    discovered: set[int] = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in discovered:
            continue
        discovered.add(pid)
        pending.extend(
            child_pid for child_pid, parent_pid in parent_by_pid.items() if parent_pid == pid
        )
    return discovered


def process_rss_bytes(pids: set[int]) -> int:
    page_size = os.sysconf("SC_PAGE_SIZE")
    total = 0
    for pid in pids:
        try:
            fields = Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if len(fields) >= 2:
            total += int(fields[1]) * page_size
    return total


def process_tree_rss_bytes(root_pid: int) -> int:
    return process_rss_bytes(process_tree_pids(root_pid))


def memory_summary(samples: list[int]) -> dict[str, Any]:
    if not samples:
        raise RuntimeError("No process memory samples were captured")
    divisor = 1024 * 1024
    stable_window = samples[-min(20, len(samples)) :]
    return {
        "baselineMiB": round(samples[0] / divisor, 3),
        "peakMiB": round(max(samples) / divisor, 3),
        "sampleCount": len(samples),
        "stableMiB": round(statistics.median(stable_window) / divisor, 3),
    }


async def sample_memory(
    process_trees: dict[str, set[int]],
    samples: dict[str, list[int]],
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        for target, pids in process_trees.items():
            samples[target].append(process_rss_bytes(pids))
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=0.05)


def read_pid(path: Path) -> int:
    value = path.read_text(encoding="ascii").strip()
    if not value.isdigit():
        raise RuntimeError(f"Invalid PID file: {path}")
    return int(value)


async def capture(args: argparse.Namespace) -> dict[str, Any]:
    import httpx

    concurrencies = [int(value) for value in args.concurrency.split(",")]
    max_concurrency = max(concurrencies)
    limits = httpx.Limits(
        max_connections=max_concurrency,
        max_keepalive_connections=max_concurrency,
    )
    timeout = httpx.Timeout(args.timeout)
    urls = {
        "java": f"{args.java_url}{args.path}",
        "python": f"{args.python_url}{args.path}",
    }
    roots = {
        "java": read_pid(args.java_pid_file),
        "python": read_pid(args.python_pid_file),
    }
    process_trees = {target: process_tree_pids(root_pid) for target, root_pid in roots.items()}
    memory_samples: dict[str, list[int]] = {"java": [], "python": []}
    memory_stop = asyncio.Event()
    async with (
        httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            trust_env=False,
        ) as java_client,
        httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            trust_env=False,
        ) as python_client,
    ):
        clients = {"java": java_client, "python": python_client}
        for target in ("java", "python"):
            for _ in range(args.warmup):
                result = await request_once(
                    clients[target],
                    urls[target],
                    asyncio.Semaphore(1),
                    httpx.HTTPError,
                )
                if "error" in result:
                    raise RuntimeError(f"{target} warmup failed: {result['error']}")

        memory_task = asyncio.create_task(sample_memory(process_trees, memory_samples, memory_stop))
        scenarios: dict[str, Any] = {}
        try:
            for concurrency in concurrencies:
                target_rounds: dict[str, list[dict[str, Any]]] = {
                    "java": [],
                    "python": [],
                }
                for round_index in range(args.rounds):
                    order = ("java", "python") if round_index % 2 == 0 else ("python", "java")
                    for target in order:
                        target_rounds[target].append(
                            await run_round(
                                clients[target],
                                urls[target],
                                concurrency,
                                args.requests,
                                httpx.HTTPError,
                            )
                        )
                scenarios[str(concurrency)] = compare_scenario(
                    summarize(target_rounds["java"]),
                    summarize(target_rounds["python"]),
                )
        finally:
            memory_stop.set()
            await memory_task
    memory = {target: memory_summary(samples) for target, samples in memory_samples.items()}
    stable_allowed = float(memory["java"]["stableMiB"]) * 1.20
    memory_passed = float(memory["python"]["stableMiB"]) <= stable_allowed
    return {
        "fakeModel": False,
        "memory": {
            "criteria": {"pythonStableAllowedMiB": round(stable_allowed, 3)},
            "java": memory["java"],
            "passed": memory_passed,
            "python": memory["python"],
        },
        "modelCalls": 0,
        "passed": (all(scenario["passed"] for scenario in scenarios.values()) and memory_passed),
        "path": args.path,
        "realModelValidated": False,
        "scenarios": scenarios,
        "scope": "Deterministic no-model REST at concurrency 1, 10, and 50",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", default="1,10,50")
    parser.add_argument("--java-pid-file", type=Path, required=True)
    parser.add_argument("--java-url", default="http://127.0.0.1:18080")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--path", default="/api/interview/skills/python-backend")
    parser.add_argument("--python-pid-file", type=Path, required=True)
    parser.add_argument("--python-url", default="http://127.0.0.1:28080")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()
    concurrencies = [int(value) for value in args.concurrency.split(",")]
    if args.requests < max(concurrencies) or args.rounds < 2:
        raise SystemExit("requests must cover max concurrency and rounds must be at least 2")

    report = asyncio.run(capture(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        raise SystemExit(f"REST performance comparison failed: {args.output}")


if __name__ == "__main__":
    main()
