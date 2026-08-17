#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def question_count(user_prompt: str) -> int:
    match = re.search(r"请生成共 (-?\d+) 个", user_prompt)
    return max(0, int(match.group(1))) if match else 0


def response_content(messages: list[dict[str, Any]]) -> dict[str, Any]:
    system = str(messages[0].get("content") or "") if messages else ""
    user = str(messages[-1].get("content") or "") if messages else ""
    if "招聘专家" in system:
        return {
            "categories": [
                {
                    "key": "JAVA",
                    "label": "Java",
                    "priority": "CORE",
                    "ref": "java-core.md",
                    "shared": False,
                },
                {
                    "key": "MYSQL",
                    "label": "MySQL",
                    "priority": "NORMAL",
                    "ref": "mysql.md",
                    "shared": True,
                },
                {
                    "key": "REDIS",
                    "label": "Redis",
                    "priority": "NORMAL",
                    "ref": "redis.md",
                    "shared": True,
                },
            ]
        }
    if "项目经历深度追问" in system or "经验丰富的技术面试官" in system:
        prefix = "简历题" if "项目经历深度追问" in system else "方向题"
        return {
            "questions": [
                {
                    "question": f"{prefix}{index + 1}：请解释固定技术主题。",
                    "type": "JAVA",
                    "category": "Java",
                    "topicSummary": f"固定主题{index + 1}",
                    "followUps": [f"{prefix}{index + 1}的固定追问。"],
                }
                for index in range(question_count(user))
            ]
        }
    if "10 年以上经验" in system:
        indices = [int(value) - 1 for value in re.findall(r"问题(\d+) \[", user)]
        return {
            "overallScore": 80,
            "overallFeedback": "固定批次评价",
            "strengths": ["回答准确"],
            "improvements": ["补充边界条件"],
            "questionEvaluations": [
                {
                    "questionIndex": index,
                    "score": 80,
                    "feedback": "固定逐题反馈",
                    "referenceAnswer": "固定参考答案",
                    "keyPoints": ["固定要点"],
                }
                for index in indices
            ],
        }
    if "资深技术面试评审专家" in system:
        return {
            "overallFeedback": "固定综合评价",
            "strengths": ["技术基础扎实"],
            "improvements": ["继续深入原理"],
        }
    return {"message": "ok"}


class StubHandler(BaseHTTPRequestHandler):
    server_version = "InterviewModelStub/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json({"status": "UP"})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if not self.path.rstrip("/").endswith("chat/completions"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.server.record_path.parent.mkdir(parents=True, exist_ok=True)
        with self.server.record_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        content = response_content(list(payload.get("messages") or []))
        self._json(
            {
                "id": "chatcmpl-interview-comparison",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model", "comparison-model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                content,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _json(self, payload: dict[str, Any]) -> None:
        content = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class StubServer(ThreadingHTTPServer):
    record_path: Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18100)
    parser.add_argument("--record", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.record.write_text("", encoding="utf-8")
    server = StubServer((arguments.host, arguments.port), StubHandler)
    server.record_path = arguments.record
    server.serve_forever()


if __name__ == "__main__":
    main()
