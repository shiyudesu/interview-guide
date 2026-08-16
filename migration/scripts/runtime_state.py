#!/usr/bin/env python3
"""Capture deterministic PostgreSQL dump, Redis, and S3 runtime state."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

SCHEMA_VERSION = 1


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def normalize_dump(value: str) -> str:
    ignored_prefixes = (
        "-- Dumped from database version",
        "-- Dumped by pg_dump version",
        "\\restrict ",
        "\\unrestrict ",
    )
    lines = [
        line.rstrip()
        for line in value.replace("\r\n", "\n").splitlines()
        if not line.startswith(ignored_prefixes)
    ]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def decode_bytes(value: bytes) -> str | dict[str, str]:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "base64": base64.b64encode(value).decode("ascii"),
            "sha256": hashlib.sha256(value).hexdigest(),
        }


def decode_redis(value: Any) -> Any:
    if isinstance(value, bytes):
        return decode_bytes(value)
    if isinstance(value, list):
        return [decode_redis(item) for item in value]
    return value


class RedisClient:
    def __init__(self, host: str, port: int) -> None:
        self._socket = socket.create_connection((host, port), timeout=10)
        self._stream = self._socket.makefile("rwb", buffering=0)

    def close(self) -> None:
        self._stream.close()
        self._socket.close()

    def command(self, *parts: str | bytes | int) -> Any:
        encoded = [
            part
            if isinstance(part, bytes)
            else str(part).encode("utf-8")
            for part in parts
        ]
        request = [f"*{len(encoded)}\r\n".encode("ascii")]
        for part in encoded:
            request.extend(
                [
                    f"${len(part)}\r\n".encode("ascii"),
                    part,
                    b"\r\n",
                ]
            )
        self._socket.sendall(b"".join(request))
        return self._read_response(self._stream)

    @classmethod
    def _read_response(cls, stream: BinaryIO) -> Any:
        prefix = stream.read(1)
        if not prefix:
            raise ConnectionError("Redis connection closed")
        line = stream.readline()
        if not line.endswith(b"\r\n"):
            raise ValueError("Invalid Redis response")
        content = line[:-2]
        if prefix == b"+":
            return content
        if prefix == b"-":
            raise RuntimeError(content.decode("utf-8", errors="replace"))
        if prefix == b":":
            return int(content)
        if prefix == b"$":
            length = int(content)
            if length == -1:
                return None
            value = stream.read(length)
            if stream.read(2) != b"\r\n":
                raise ValueError("Invalid Redis bulk response")
            return value
        if prefix == b"*":
            length = int(content)
            if length == -1:
                return None
            return [cls._read_response(stream) for _ in range(length)]
        raise ValueError(f"Unsupported Redis response prefix: {prefix!r}")


def pairs(values: list[Any]) -> list[dict[str, Any]]:
    return [
        {"key": decode_redis(values[index]), "value": decode_redis(values[index + 1])}
        for index in range(0, len(values), 2)
    ]


def stream_entries(values: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "fields": pairs(entry[1]),
            "id": decode_redis(entry[0]),
        }
        for entry in values
    ]


def stream_groups(values: list[Any]) -> list[dict[str, Any]]:
    groups = [
        {
            str(decode_redis(entry[index])): decode_redis(entry[index + 1])
            for index in range(0, len(entry), 2)
        }
        for entry in values
    ]
    return sorted(groups, key=lambda item: str(item.get("name", "")))


def stream_consumers(
    client: RedisClient,
    key: bytes,
    group_name: str,
) -> list[dict[str, Any]]:
    values = client.command("XINFO", "CONSUMERS", key, group_name)
    consumers = []
    for entry in values:
        details = {
            str(decode_redis(entry[index])): decode_redis(entry[index + 1])
            for index in range(0, len(entry), 2)
        }
        consumers.append(
            {
                "name": details["name"],
                "pending": details["pending"],
            }
        )
    return sorted(consumers, key=lambda item: str(item["name"]))


def redis_value(client: RedisClient, key: bytes, value_type: str) -> Any:
    if value_type == "string":
        return decode_redis(client.command("GET", key))
    if value_type == "hash":
        return sorted(
            pairs(client.command("HGETALL", key)),
            key=lambda item: json.dumps(item["key"], sort_keys=True),
        )
    if value_type == "list":
        return decode_redis(client.command("LRANGE", key, 0, -1))
    if value_type == "set":
        values = decode_redis(client.command("SMEMBERS", key))
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True))
    if value_type == "zset":
        return pairs(client.command("ZRANGE", key, 0, -1, "WITHSCORES"))
    if value_type == "stream":
        groups = stream_groups(client.command("XINFO", "GROUPS", key))
        return {
            "entries": stream_entries(client.command("XRANGE", key, "-", "+")),
            "groups": [
                {
                    **group,
                    "consumerDetails": stream_consumers(
                        client,
                        key,
                        str(group["name"]),
                    ),
                }
                for group in groups
            ],
            "pending": [
                {
                    "group": group["name"],
                    "summary": decode_redis(
                        client.command("XPENDING", key, group["name"])
                    ),
                }
                for group in groups
            ],
        }
    return {"unsupportedType": value_type}


def capture_redis(host: str, port: int) -> dict[str, Any]:
    client = RedisClient(host, port)
    try:
        cursor: bytes | int = b"0"
        keys: list[bytes] = []
        while True:
            cursor, page = client.command("SCAN", cursor, "COUNT", 1000)
            keys.extend(page)
            if cursor == b"0":
                break
        records = []
        for key in sorted(keys):
            value_type = client.command("TYPE", key).decode("ascii")
            ttl_ms = client.command("PTTL", key)
            ttl: dict[str, Any]
            if ttl_ms == -1:
                ttl = {"kind": "persistent"}
            elif ttl_ms == -2:
                ttl = {"kind": "missing"}
            else:
                ttl = {
                    "kind": "expiring",
                    "milliseconds": ttl_ms,
                    "secondsCeiling": (ttl_ms + 999) // 1000,
                }
            records.append(
                {
                    "key": decode_bytes(key),
                    "ttl": ttl,
                    "type": value_type,
                    "value": redis_value(client, key, value_type),
                }
            )
        return {"keys": records}
    finally:
        client.close()


class S3Client:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        parsed = urllib.parse.urlsplit(endpoint.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("S3 endpoint must be an HTTP(S) URL")
        self._endpoint = parsed
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region

    @staticmethod
    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    def request(
        self,
        method: str,
        path: str,
        query: list[tuple[str, str]] | None = None,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_uri = urllib.parse.quote(path, safe="/-_.~")
        query_items = sorted(query or [])
        canonical_query = "&".join(
            f"{urllib.parse.quote(key, safe='-_.~')}="
            f"{urllib.parse.quote(value, safe='-_.~')}"
            for key, value in query_items
        )
        request_headers = {
            key.lower(): " ".join(value.strip().split())
            for key, value in (headers or {}).items()
        }
        request_headers.update(
            {
                "host": self._endpoint.netloc,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
            }
        )
        signed_header_names = sorted(request_headers)
        canonical_headers = "".join(
            f"{name}:{request_headers[name]}\n" for name in signed_header_names
        )
        signed_headers = ";".join(signed_header_names)
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                canonical_query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        date_key = self._sign(
            f"AWS4{self._secret_key}".encode("utf-8"),
            date_stamp,
        )
        region_key = self._sign(date_key, self._region)
        service_key = self._sign(region_key, "s3")
        signing_key = self._sign(service_key, "aws4_request")
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self._access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request_headers["authorization"] = authorization
        query_string = f"?{canonical_query}" if canonical_query else ""
        url = urllib.parse.urlunsplit(
            (
                self._endpoint.scheme,
                self._endpoint.netloc,
                canonical_uri,
                query_string[1:],
                "",
            )
        )
        request = urllib.request.Request(
            url,
            data=body if method in {"POST", "PUT"} else None,
            headers=request_headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        return (
            response.status,
            {key.lower(): value for key, value in response.headers.items()},
            response.read(),
        )

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        headers = {
            "content-type": content_type,
            **{f"x-amz-meta-{name}": value for name, value in metadata.items()},
        }
        status, _, response_body = self.request(
            "PUT",
            f"/{bucket}/{key}",
            body=body,
            headers=headers,
        )
        if status not in {200, 201}:
            raise RuntimeError(
                f"S3 PUT failed with status {status}: "
                f"{response_body.decode('utf-8', errors='replace')}"
            )

    def list_objects(self, bucket: str) -> list[str]:
        continuation: str | None = None
        keys: list[str] = []
        while True:
            query = [("list-type", "2")]
            if continuation is not None:
                query.append(("continuation-token", continuation))
            status, _, body = self.request("GET", f"/{bucket}", query=query)
            if status != 200:
                raise RuntimeError(
                    f"S3 list failed with status {status}: "
                    f"{body.decode('utf-8', errors='replace')}"
                )
            root = ET.fromstring(body)
            namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            keys.extend(
                element.text or ""
                for element in root.findall("s3:Contents/s3:Key", namespace)
            )
            truncated = (
                root.findtext("s3:IsTruncated", "false", namespace).lower()
                == "true"
            )
            if not truncated:
                return sorted(keys)
            continuation = root.findtext("s3:NextContinuationToken", None, namespace)
            if continuation is None:
                raise RuntimeError("S3 list response omitted continuation token")

    def capture_bucket(self, bucket: str) -> dict[str, Any]:
        objects = []
        for key in self.list_objects(bucket):
            status, headers, body = self.request("GET", f"/{bucket}/{key}")
            if status != 200:
                raise RuntimeError(f"S3 GET failed for {key}: HTTP {status}")
            tracked_headers = {
                name: value
                for name, value in headers.items()
                if name
                in {
                    "accept-ranges",
                    "content-length",
                    "content-type",
                    "etag",
                }
                or name.startswith("x-amz-meta-")
            }
            objects.append(
                {
                    "bytes": len(body),
                    "headers": dict(sorted(tracked_headers.items())),
                    "key": key,
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            )
        return {"bucket": "{{BUCKET}}", "objects": objects}


def s3_client(args: argparse.Namespace) -> S3Client:
    return S3Client(
        args.s3_endpoint,
        args.s3_access_key,
        args.s3_secret_key,
        args.s3_region,
    )


def seed_s3(args: argparse.Namespace) -> int:
    s3_client(args).put_object(
        args.s3_bucket,
        args.key,
        args.content.encode("utf-8"),
        "text/plain; charset=utf-8",
        {"fixture": "migration-comparison"},
    )
    return 0


def capture(args: argparse.Namespace) -> int:
    database_dump = normalize_dump(
        args.database_data.read_text(encoding="utf-8")
    )
    document = {
        "databaseData": database_dump,
        "redis": capture_redis(args.redis_host, args.redis_port),
        "s3": s3_client(args).capture_bucket(args.s3_bucket),
        "schemaVersion": SCHEMA_VERSION,
    }
    write_json(args.output, document)
    return 0


def add_s3_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--s3-access-key", required=True)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-endpoint", required=True)
    parser.add_argument("--s3-region", default="us-east-1")
    parser.add_argument("--s3-secret-key", required=True)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    subparsers = argument_parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--database-data", type=Path, required=True)
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--redis-host", default="127.0.0.1")
    capture_parser.add_argument("--redis-port", type=int, required=True)
    add_s3_arguments(capture_parser)
    capture_parser.set_defaults(handler=capture)

    seed_parser = subparsers.add_parser("seed-s3")
    seed_parser.add_argument("--content", required=True)
    seed_parser.add_argument("--key", required=True)
    add_s3_arguments(seed_parser)
    seed_parser.set_defaults(handler=seed_s3)
    return argument_parser


def main() -> None:
    args = parser().parse_args()
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
