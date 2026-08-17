#!/usr/bin/env python3
"""Alternate real-provider calls and compare Java/Python application latency."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

QWEN35_FLASH_PRICING = {
    "inputPerMillionUsd": 0.029,
    "outputPerMillionUsd": 0.287,
    "source": "https://www.alibabacloud.com/help/en/model-studio/qwen3-5-flash",
    "tier": "China (Beijing), input <= 128K",
    "verifiedAt": "2026-04-10",
}


def call(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, data=b"", method="POST")
    started = time.perf_counter_ns()
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read())
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    if body.get("code") != 200 or not (body.get("data") or {}).get("success"):
        raise RuntimeError(f"Real-provider performance call failed: {body}")
    return {
        "elapsedMs": round(elapsed_ms, 3),
        "model": body["data"]["model"],
        "response": body,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))
    return ordered[index]


def summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(sample["elapsedMs"]) for sample in samples]
    return {
        "count": len(values),
        "medianMs": round(statistics.median(values), 3),
        "p95Ms": round(percentile(values, 0.95), 3),
        "p99Ms": round(percentile(values, 0.99), 3),
        "samples": samples,
    }


def record_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def response_usage(event: dict[str, Any]) -> dict[str, int]:
    body = event.get("body")
    document = body.get("json") if isinstance(body, dict) else None
    usage = document.get("usage") if isinstance(document, dict) else None
    if not isinstance(usage, dict):
        return {"inputTokens": 0, "outputTokens": 0}
    return {
        "inputTokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "outputTokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
    }


def estimated_cost(model: str, usage: dict[str, int]) -> dict[str, Any]:
    if model != "qwen3.5-flash":
        return {
            "currency": "USD",
            "estimated": None,
            "reason": f"No versioned price configured for {model}",
        }
    value = (
        usage["inputTokens"] * QWEN35_FLASH_PRICING["inputPerMillionUsd"]
        + usage["outputTokens"] * QWEN35_FLASH_PRICING["outputPerMillionUsd"]
    ) / 1_000_000
    return {
        "currency": "USD",
        "estimated": round(value, 9),
        "pricing": QWEN35_FLASH_PRICING,
    }


def proxy_capture(
    path: Path,
    start_line: int,
    expected_calls: int,
) -> dict[str, Any]:
    events = [json.loads(line) for line in record_lines(path)[start_line:]]
    requests = [event for event in events if event.get("kind") == "http-request"]
    responses = {
        event.get("correlationId"): event
        for event in events
        if event.get("kind") == "http-response"
    }
    if len(requests) != expected_calls or len(responses) != expected_calls:
        raise RuntimeError(
            "Expected "
            f"{expected_calls} proxy request/response records, got "
            f"{len(requests)}/{len(responses)}"
        )

    targets: dict[str, dict[str, Any]] = {
        "java": {"networkSamplesMs": [], "usage": {"inputTokens": 0, "outputTokens": 0}},
        "python": {
            "networkSamplesMs": [],
            "usage": {"inputTokens": 0, "outputTokens": 0},
        },
    }
    request_documents: list[dict[str, Any]] = []
    for index, request in enumerate(requests):
        target = "java" if index % 2 == 0 else "python"
        body = request.get("body")
        document = body.get("json") if isinstance(body, dict) else None
        if not isinstance(document, dict):
            raise RuntimeError("Proxy request did not contain a JSON body")
        request_documents.append(document)
        response = responses.get(request.get("correlationId"))
        if response is None or response.get("status") != 200:
            raise RuntimeError(f"Missing successful proxy response for request {index}")
        targets[target]["networkSamplesMs"].append(float(response["durationMs"]))
        usage = response_usage(response)
        for key in ("inputTokens", "outputTokens"):
            targets[target]["usage"][key] += usage[key]

    canonical_requests = {
        json.dumps(document, ensure_ascii=False, sort_keys=True) for document in request_documents
    }
    model = str(request_documents[0].get("model", ""))
    for target in targets.values():
        network_values = target.pop("networkSamplesMs")
        target["providerNetwork"] = {
            "count": len(network_values),
            "medianMs": round(statistics.median(network_values), 3),
            "p95Ms": round(percentile(network_values, 0.95), 3),
            "p99Ms": round(percentile(network_values, 0.99), 3),
            "samplesMs": network_values,
        }
        target["cost"] = estimated_cost(model, target["usage"])
    return {
        "calls": expected_calls,
        "model": model,
        "request": request_documents[0],
        "requestsIdentical": len(canonical_requests) == 1,
        "targets": targets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--java-url", default="http://127.0.0.1:18080")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--proxy-log", type=Path, required=True)
    parser.add_argument("--python-url", default="http://127.0.0.1:28080")
    args = parser.parse_args()
    if args.iterations < 5:
        raise SystemExit("--iterations must be at least 5")

    proxy_start_line = len(record_lines(args.proxy_log))
    samples: dict[str, list[dict[str, Any]]] = {"java": [], "python": []}
    for _ in range(args.iterations):
        samples["java"].append(call(f"{args.java_url}/api/llm-provider/dashscope/test"))
        samples["python"].append(call(f"{args.python_url}/api/llm-provider/dashscope/test"))

    provider = proxy_capture(args.proxy_log, proxy_start_line, args.iterations * 2)
    java = summary(samples["java"])
    python = summary(samples["python"])
    response_models = {
        sample["model"] for target_samples in samples.values() for sample in target_samples
    }
    java_p95 = float(java["p95Ms"])
    python_p95 = float(python["p95Ms"])
    java_p99 = float(java["p99Ms"])
    python_p99 = float(python["p99Ms"])
    report = {
        "scenario": "Provider connectivity REST, concurrency 1",
        "criteria": {
            "p95AllowedMs": round(min(java_p95 * 1.10, java_p95 + 100), 3),
            "p99AllowedMs": round(java_p99 * 1.15, 3),
        },
        "java": java,
        "passed": (
            python_p95 <= min(java_p95 * 1.10, java_p95 + 100)
            and python_p99 <= java_p99 * 1.15
            and provider["requestsIdentical"]
            and response_models == {provider["model"]}
            and all(target["usage"]["inputTokens"] > 0 for target in provider["targets"].values())
        ),
        "provider": provider,
        "python": python,
        "realModelValidated": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        raise SystemExit(f"Performance acceptance failed: {args.output}")


if __name__ == "__main__":
    main()
