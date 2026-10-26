from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

ENDPOINT = os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000").rstrip("/")
ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
SECRET_KEY = os.getenv("S3_SECRET_KEY")
REGION = os.getenv("S3_REGION", "us-east-1")
OPENER = build_opener(ProxyHandler({}))


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def request(method: str, path: str, body: bytes = b"", extra_headers: dict | None = None):
    if not ACCESS_KEY or not SECRET_KEY:
        raise RuntimeError("Set S3_ACCESS_KEY and S3_SECRET_KEY in the environment")
    now = datetime.now(UTC)
    stamp, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    digest = hashlib.sha256(body).hexdigest()
    host = ENDPOINT.split("//", 1)[1]
    headers = {"host": host, "x-amz-content-sha256": digest, "x-amz-date": stamp}
    if extra_headers:
        headers.update({k.lower(): v for k, v in extra_headers.items()})
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers.items()))
    signed = ";".join(sorted(headers))
    uri = quote(path, safe="/-_.~")
    canonical = "\n".join((method, uri, "", canonical_headers, signed, digest))
    scope = f"{date}/{REGION}/s3/aws4_request"
    string = "\n".join(("AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()))
    key = _sign(_sign(_sign(_sign(("AWS4" + SECRET_KEY).encode(), date), REGION), "s3"), "aws4_request")
    signature = hmac.new(key, string.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{scope}, SignedHeaders={signed}, Signature={signature}"
    return OPENER.open(Request(ENDPOINT + uri, data=body if method in ("PUT", "POST") else None,
                               method=method, headers=headers), timeout=120)


def put(bucket: str, key: str, payload: bytes):
    with request("PUT", f"/{bucket}/{key}", payload) as response:
        return {"status": response.status, "etag": response.headers.get("ETag"), "bytes": len(payload)}


def create_bucket(bucket: str):
    with request("PUT", f"/{bucket}") as response:
        return response.status


def get(bucket: str, key: str):
    return request("GET", f"/{bucket}/{key}")


def head(bucket: str, key: str):
    with request("HEAD", f"/{bucket}/{key}") as response:
        return {"status": response.status, "bytes": int(response.headers["Content-Length"]),
                "etag": response.headers.get("ETag")}
