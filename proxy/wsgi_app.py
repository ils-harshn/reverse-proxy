"""Sync WSGI app — fast import and reload on PythonAnywhere (no Starlette/a2wsgi)."""

from __future__ import annotations

from typing import Callable

import httpx

from proxy.config import Settings, load_settings
from proxy.headers import (
    filter_request_headers,
    filter_response_headers,
    rewrite_location,
)
from proxy.upstream import build_upstream_url

REDIRECT_STATUS = {301, 302, 303, 307, 308}
HEALTH_PATH = "/_proxy/health"
ALLOWED_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)


def _headers_from_environ(environ: dict, upstream_host: str) -> dict[str, str]:
    raw: list[tuple[bytes, bytes]] = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").lower().encode("latin-1")
            raw.append((name, value.encode("latin-1")))
    if environ.get("CONTENT_TYPE"):
        raw.append((b"content-type", environ["CONTENT_TYPE"].encode("latin-1")))
    if environ.get("CONTENT_LENGTH"):
        raw.append((b"content-length", environ["CONTENT_LENGTH"].encode("latin-1")))
    return filter_request_headers(raw, upstream_host)


def _status_line(code: int) -> str:
    phrases = {
        200: "OK",
        301: "Moved Permanently",
        302: "Found",
        303: "See Other",
        307: "Temporary Redirect",
        308: "Permanent Redirect",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        502: "Bad Gateway",
    }
    return f"{code} {phrases.get(code, 'Unknown')}"


def create_wsgi_application(
    settings: Settings | None = None,
) -> Callable[..., list[bytes]]:
    settings = settings or load_settings()
    from urllib.parse import urlparse

    parsed_base = urlparse(settings.base_url)
    upstream_host = parsed_base.netloc
    client = httpx.Client(
        follow_redirects=False,
        timeout=httpx.Timeout(settings.upstream_timeout),
        trust_env=not settings.ignore_env,
    )

    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "") or "/"

        if path == HEALTH_PATH and method == "GET":
            body = b'{"status":"ok"}'
            start_response(
                "200 OK",
                [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            )
            return [body]

        if method not in ALLOWED_METHODS:
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
            return [b"Method not allowed"]

        query_string = environ.get("QUERY_STRING", "")
        upstream_url = build_upstream_url(settings, path, query_string)
        headers = _headers_from_environ(environ, upstream_host)

        length = environ.get("CONTENT_LENGTH")
        body: bytes | None = None
        if length and int(length) > 0:
            body = environ["wsgi.input"].read(int(length))

        try:
            upstream = client.request(
                method,
                upstream_url,
                content=body,
                headers=headers,
            )
        except httpx.RequestError as exc:
            msg = f"Upstream request failed: {exc}".encode()
            start_response("502 Bad Gateway", [("Content-Type", "text/plain")])
            return [msg]

        response_headers = filter_response_headers(upstream.headers)
        status = _status_line(upstream.status_code)

        if upstream.status_code in REDIRECT_STATUS:
            location = upstream.headers.get("location")
            if location:
                location = rewrite_location(
                    location, settings.base_origin, settings.public_url
                )
                out_headers = [
                    (k, v)
                    for k, v in response_headers
                    if k.lower() not in ("location", "content-length", "content-type")
                ]
                out_headers.append(("Location", location))
                start_response(status, out_headers)
                return [b""]

        out_headers = [(k, v) for k, v in response_headers]
        if upstream.status_code == 200 and "Content-Length" not in {
            k for k, _ in out_headers
        }:
            out_headers.append(("Content-Length", str(len(upstream.content))))

        start_response(status, out_headers)
        if method == "HEAD":
            return [b""]
        return [upstream.content]

    return application


_inner: Callable | None = None


def application(environ, start_response):
    global _inner
    if _inner is None:
        _inner = create_wsgi_application()
    return _inner(environ, start_response)