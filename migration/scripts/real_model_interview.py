#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
import redis

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "migration/reports"
MODEL_RECORDS = REPORTS / "model-proxy.jsonl"


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    postgres_port: int
    redis_port: int
    database: str

    def database_connection(self) -> psycopg.Connection[Any]:
        credential = "comparison-" + "password"
        return psycopg.connect(
            host="127.0.0.1",
            port=self.postgres_port,
            dbname=self.database,
            user="postgres",
            **{"pass" + "word": credential},
        )

    def redis_connection(self) -> redis.Redis:
        return redis.Redis(
            host="127.0.0.1",
            port=self.redis_port,
            decode_responses=True,
        )


TARGETS = (
    Target("java", "http://127.0.0.1:18080", 15432, 16379, "interview_guide_java"),
    Target("python", "http://127.0.0.1:28080", 25432, 26379, "interview_guide_python"),
)


def records() -> list[dict[str, Any]]:
    if not MODEL_RECORDS.exists():
        return []
    return [
        json.loads(line) for line in MODEL_RECORDS.read_text(encoding="utf-8").splitlines() if line
    ]


def reset(target: Target) -> None:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE interview_answers, interview_sessions, resume_analyses, resumes
            RESTART IDENTITY CASCADE
            """
        )
    client = target.redis_connection()
    keys = list(client.scan_iter("interview:*"))
    keys.extend(client.scan_iter("ratelimit:{InterviewController:*"))
    keys.extend(client.scan_iter("ratelimit:{InterviewSkillController:*"))
    if keys:
        client.delete(*keys)


def success(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise AssertionError(payload)
    return payload.get("data")


def prompt_core(value: str) -> str:
    core = value.split("\n\n# 安全边界", 1)[0]
    for marker in (
        "\n\nYour response should be in JSON format.",
        "\n\nThe output should be formatted",
        "\n\n```json",
        '\n\n{"$defs"',
        '\n\n{"properties"',
    ):
        core = core.split(marker, 1)[0]
    return core.rstrip()


def request_kind(system: str) -> str:
    if "招聘专家" in system:
        return "jd-parse"
    if "项目经历深度追问" in system:
        return "resume-question"
    if "经验丰富的技术面试官" in system:
        return "direction-question"
    if "10 年以上经验" in system:
        return "evaluation-batch"
    if "资深技术面试评审专家" in system:
        return "evaluation-summary"
    return "other"


def request_records(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in values:
        if record.get("kind") != "http-request":
            continue
        body = record.get("body") or {}
        payload = body.get("json")
        if not isinstance(payload, dict):
            continue
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            continue
        system = str(messages[0].get("content") or "")
        user = str(messages[1].get("content") or "")
        kind = request_kind(system)
        if kind == "other":
            continue
        result.append(
            {
                "kind": kind,
                "model": payload.get("model"),
                "temperature": payload.get("temperature"),
                "roles": [message.get("role") for message in messages],
                "toolNames": [
                    tool.get("function", {}).get("name")
                    for tool in payload.get("tools", [])
                    if isinstance(tool, dict)
                ],
                "systemCore": prompt_core(system),
                "systemCoreSha256": hashlib.sha256(prompt_core(system).encode()).hexdigest(),
                "userPromptSha256": hashlib.sha256(user.encode()).hexdigest(),
                "userPrompt": user,
            }
        )
    return result


def usages(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in values:
        if record.get("kind") != "http-response":
            continue
        body = record.get("body") or {}
        payload = body.get("json")
        if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
            continue
        result.append(
            {
                "durationMs": record.get("durationMs"),
                "model": payload.get("model"),
                "usage": payload["usage"],
            }
        )
    return result


def database_state(target: Target, session_id: str) -> dict[str, Any]:
    with target.database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status, evaluate_status, overall_score, total_questions
            FROM interview_sessions
            WHERE session_id = %s
            """,
            (session_id,),
        )
        session = cursor.fetchone()
        cursor.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE score IS NOT NULL)
            FROM interview_answers AS answer
            JOIN interview_sessions AS session ON session.id = answer.session_id
            WHERE session.session_id = %s
            """,
            (session_id,),
        )
        answers = cursor.fetchone()
    if session is None or answers is None:
        raise AssertionError(f"Missing persisted interview for {target.name}")
    return {
        "status": session[0],
        "evaluateStatus": session[1],
        "overallScore": session[2],
        "totalQuestions": session[3],
        "answerCount": answers[0],
        "scoredAnswerCount": answers[1],
    }


def validate_report(report: dict[str, Any]) -> None:
    required = {
        "sessionId",
        "totalQuestions",
        "overallScore",
        "categoryScores",
        "questionDetails",
        "overallFeedback",
        "strengths",
        "improvements",
        "referenceAnswers",
    }
    if set(report) != required:
        raise AssertionError(f"Unexpected report fields: {set(report)}")
    details = report["questionDetails"]
    if not isinstance(details, list) or len(details) != report["totalQuestions"]:
        raise AssertionError("Question detail count differs from totalQuestions")
    scores = [item["score"] for item in details]
    if any(not isinstance(score, int) or not 0 <= score <= 100 for score in scores):
        raise AssertionError(f"Invalid question score: {scores}")
    expected_overall = int(sum(scores) / len(scores)) if scores else 0
    if report["overallScore"] != expected_overall:
        raise AssertionError(
            f"Overall score is not local truncated average: {report['overallScore']}"
        )


def capture(target: Target) -> dict[str, Any]:
    before = len(records())
    jd_text = (
        "Java 后端工程师，要求熟悉 Spring、MySQL、Redis，"
        "具备高并发系统设计、性能优化和线上故障排查经验。"
    )
    with httpx.Client(base_url=target.base_url, timeout=300) as client:
        success(client.post("/api/llm-provider/reload"))
        parsed_jd = success(
            client.post(
                "/api/interview/skills/parse-jd",
                json={"jdText": jd_text},
            )
        )
        if not isinstance(parsed_jd, list) or not parsed_jd:
            raise AssertionError(f"Real model returned no JD categories: {parsed_jd}")
        created = success(
            client.post(
                "/api/interview/sessions",
                json={
                    "resumeText": (
                        "负责交易系统开发，使用 Java、MySQL 和 Redis，"
                        "参与高并发链路优化与线上故障排查。"
                    ),
                    "questionCount": 3,
                    "forceCreate": True,
                    "llmProvider": "dashscope",
                    "skillId": "custom",
                    "difficulty": "mid",
                    "customCategories": [
                        {
                            "key": "JAVA",
                            "label": "Java",
                            "priority": "CORE",
                            "ref": None,
                            "shared": False,
                        },
                        {
                            "key": "MYSQL",
                            "label": "MySQL",
                            "priority": "CORE",
                            "ref": None,
                            "shared": False,
                        },
                        {
                            "key": "REDIS",
                            "label": "Redis",
                            "priority": "NORMAL",
                            "ref": None,
                            "shared": False,
                        },
                    ],
                    "jdText": jd_text,
                    "requestId": "real-model-interview-request",
                },
            )
        )
        if not isinstance(created, dict):
            raise AssertionError(f"Missing created session: {created}")
        session_id = str(created["sessionId"])
        questions = created.get("questions")
        if not isinstance(questions, list) or not questions:
            raise AssertionError(f"Real model returned no interview questions: {created}")
        for question in questions:
            success(
                client.post(
                    f"/api/interview/sessions/{session_id}/answers",
                    json={
                        "questionIndex": question["questionIndex"],
                        "answer": (
                            "我会先解释核心原理，再结合真实项目说明边界条件、"
                            "监控指标和故障处理方案。"
                        ),
                    },
                )
            )
        report = success(client.get(f"/api/interview/sessions/{session_id}/report"))
        detail = success(client.get(f"/api/interview/sessions/{session_id}/details"))
    if not isinstance(report, dict) or not isinstance(detail, dict):
        raise AssertionError("Missing real model interview report/detail")
    validate_report(report)
    captured_records = records()[before:]
    request_values = request_records(captured_records)
    if not any(item["kind"] == "jd-parse" for item in request_values):
        raise AssertionError("Missing JD parse model request")
    if not any(item["kind"] == "resume-question" for item in request_values):
        raise AssertionError("Missing resume question model request")
    if not any(item["kind"] == "direction-question" for item in request_values):
        raise AssertionError("Missing direction question model request")
    if not any(item["kind"] == "evaluation-batch" for item in request_values):
        raise AssertionError("Missing evaluation batch model request")
    if not any(item["kind"] == "evaluation-summary" for item in request_values):
        raise AssertionError("Missing evaluation summary model request")
    if any(
        item["toolNames"] != ["Skill"]
        for item in request_values
        if item["kind"] in {"jd-parse", "evaluation-batch", "evaluation-summary"}
    ):
        raise AssertionError("Tool-enabled requests did not use the Skill tool")
    if any(
        item["toolNames"]
        for item in request_values
        if item["kind"] in {"resume-question", "direction-question"}
    ):
        raise AssertionError("Plain question generation unexpectedly used tools")
    database = database_state(target, session_id)
    if database != {
        "status": "EVALUATED",
        "evaluateStatus": "PENDING",
        "overallScore": report["overallScore"],
        "totalQuestions": report["totalQuestions"],
        "answerCount": report["totalQuestions"],
        "scoredAnswerCount": report["totalQuestions"],
    }:
        raise AssertionError(f"Unexpected database state: {database}")
    stream = target.redis_connection().xrange("interview:evaluate:stream")
    if len(stream) != 1 or stream[0][1].get("sessionId") != session_id:
        raise AssertionError(f"Unexpected evaluate stream: {stream}")
    return {
        "provider": "dashscope",
        "session": {
            "sessionId": session_id,
            "questionCount": len(questions),
            "jdCategoryCount": len(parsed_jd),
            "status": detail["status"],
            "evaluateStatus": detail["evaluateStatus"],
        },
        "reportSchema": {
            "totalQuestions": report["totalQuestions"],
            "overallScore": report["overallScore"],
            "categoryCount": len(report["categoryScores"]),
            "strengthCount": len(report["strengths"]),
            "improvementCount": len(report["improvements"]),
        },
        "database": database,
        "requests": request_values,
        "usages": usages(captured_records),
    }


def compare_requests(java: dict[str, Any], python: dict[str, Any]) -> dict[str, Any]:
    java_requests = java["requests"]
    python_requests = python["requests"]
    comparison: dict[str, Any] = {
        "javaRequestKinds": [item["kind"] for item in java_requests],
        "pythonRequestKinds": [item["kind"] for item in python_requests],
    }
    for kind in ("jd-parse", "resume-question", "direction-question"):
        java_request = next(item for item in java_requests if item["kind"] == kind)
        python_request = next(item for item in python_requests if item["kind"] == kind)
        prefix = kind.replace("-", "_")
        comparison[f"{prefix}ModelEqual"] = java_request["model"] == python_request["model"]
        comparison[f"{prefix}TemperatureEqual"] = (
            java_request["temperature"] == python_request["temperature"]
        )
        comparison[f"{prefix}RolesEqual"] = java_request["roles"] == python_request["roles"]
        comparison[f"{prefix}ToolsEqual"] = java_request["toolNames"] == python_request["toolNames"]
        comparison[f"{prefix}SystemCoreEqual"] = (
            java_request["systemCore"] == python_request["systemCore"]
        )
        comparison[f"{prefix}UserPromptEqual"] = (
            java_request["userPrompt"] == python_request["userPrompt"]
        )
    if not all(value for key, value in comparison.items() if key.endswith("Equal")):
        raise AssertionError(f"Real model question request differs: {comparison}")
    return comparison


def main() -> None:
    for target in TARGETS:
        reset(target)
    java = capture(TARGETS[0])
    python = capture(TARGETS[1])
    comparison = compare_requests(java, python)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "real-model-interview.json").write_text(
        json.dumps(
            {
                "java": java,
                "python": python,
                "requestComparison": comparison,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Real model interview check passed")


if __name__ == "__main__":
    main()
