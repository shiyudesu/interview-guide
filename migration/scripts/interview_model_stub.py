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


def knowledge_base_question_count(user_prompt: str) -> int:
    match = re.search(r"生成 (\d+) 道面试题草稿", user_prompt)
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
    if "根据知识库内容生成可维护的面试题库草稿" in system:
        templates = [
            {
                "category": "Redis",
                "type": "REDIS",
                "question": "请说明 Redis 的两种持久化方式及其取舍。",
                "topicSummary": "Redis RDB 与 AOF 持久化",
                "referenceAnswer": "RDB 是快照，AOF 记录写命令；需要结合恢复速度与数据安全取舍。",
                "keyPoints": ["RDB", "AOF", "恢复速度", "数据安全"],
                "scoringRubric": "覆盖两种方式及取舍得满分。",
                "followUps": [
                    {
                        "question": "AOF 重写解决什么问题？",
                        "referenceAnswer": "压缩历史命令，控制 AOF 文件体积。",
                        "keyPoints": ["命令合并", "文件体积"],
                        "scoringRubric": "说明压缩历史命令得满分。",
                    },
                    {
                        "question": "如何选择持久化组合？",
                        "referenceAnswer": "根据数据安全、恢复速度和资源开销选择。",
                        "keyPoints": ["安全", "速度", "开销"],
                        "scoringRubric": "覆盖三个权衡因素得满分。",
                    },
                ],
            },
            {
                "category": "事务",
                "type": "DATABASE",
                "question": "为什么外部模型调用不应放在长数据库事务内？",
                "topicSummary": "外部调用与事务边界",
                "referenceAnswer": "长事务会持锁并放大超时与失败影响，应缩小事务边界。",
                "keyPoints": ["持锁", "超时", "失败恢复"],
                "scoringRubric": "说明锁、超时与失败恢复得满分。",
                "followUps": [
                    {
                        "question": "如何保持外部可见结果一致？",
                        "referenceAnswer": "使用状态机、幂等键和补偿恢复。",
                        "keyPoints": ["状态机", "幂等", "补偿"],
                        "scoringRubric": "覆盖状态机、幂等和补偿得满分。",
                    }
                ],
            },
        ]
        return {
            "questions": templates[: knowledge_base_question_count(user)]
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
        normalized_path = self.path.rstrip("/")
        if normalized_path.endswith("embeddings"):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self.server.record_path.parent.mkdir(parents=True, exist_ok=True)
            with self.server.record_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            inputs = payload.get("input")
            input_count = len(inputs) if isinstance(inputs, list) else 1
            dimensions = int(payload.get("dimensions") or 1024)
            embedding = [1.0] + [0.0] * (dimensions - 1)
            self._json(
                {
                    "object": "list",
                    "model": payload.get("model", "comparison-embedding"),
                    "data": [
                        {
                            "object": "embedding",
                            "index": index,
                            "embedding": embedding,
                        }
                        for index in range(input_count)
                    ],
                    "usage": {"prompt_tokens": input_count, "total_tokens": input_count},
                }
            )
            return
        if not normalized_path.endswith("chat/completions"):
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
