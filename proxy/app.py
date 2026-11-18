from urllib.parse import urlparse

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse

from proxy.config import Settings, load_settings
from proxy.headers import (
    filter_request_headers,
    filter_response_headers,
    rewrite_location,
)

REDIRECT_STATUS = {301, 302, 303, 307, 308}


def build_upstream_url(settings: Settings, request: Request) -> str:
    parsed = urlparse(settings.base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    prefix = parsed.path.rstrip("/")
    path = request.url.path
    if path == "/":
        upstream_path = prefix or "/"
    else:
        upstream_path = f"{prefix}{path}" if prefix else path
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{origin}{upstream_path}{query}"


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or load_settings()
    parsed_base = urlparse(settings.base_url)
    upstream_host = parsed_base.netloc

    client = httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(settings.upstream_timeout),
        trust_env=not settings.ignore_env,
    )

    async def proxy(request: Request) -> Response:
        upstream_url = build_upstream_url(settings, request)
        body = await request.body()
        headers = filter_request_headers(request.headers.raw, upstream_host)

        try:
            upstream = await client.request(
                request.method,
                upstream_url,
                content=body if body else None,
                headers=headers,
            )
        except httpx.RequestError as exc:
            return Response(
                content=f"Upstream request failed: {exc}",
                status_code=502,
                media_type="text/plain",
            )

        response_headers = filter_response_headers(upstream.headers)

        if upstream.status_code in REDIRECT_STATUS:
            location = upstream.headers.get("location")
            if location:
                location = rewrite_location(
                    location,
                    settings.base_origin,
                    settings.public_url,
                )
                extra = {
                    k: v
                    for k, v in response_headers
                    if k.lower() not in ("location", "content-length", "content-type")
                }
                return RedirectResponse(
                    url=location,
                    status_code=upstream.status_code,
                    headers=extra,
                )

        async def stream_body():
            async for chunk in upstream.aiter_bytes():
                yield chunk

        return StreamingResponse(
            stream_body(),
            status_code=upstream.status_code,
            headers=dict(response_headers),
        )

    async def health(_: Request) -> Response:
        return Response(content='{"status":"ok"}', media_type="application/json")

    async def on_shutdown() -> None:
        await client.aclose()

    app = Starlette(
        on_shutdown=[on_shutdown],
        routes=[],  # mounted below via middleware-style catch-all
    )
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    app.add_route("/_proxy/health", health, methods=["GET"])
    app.add_route("/", proxy, methods=methods)
    app.add_route("/{path:path}", proxy, methods=methods)
    return app


def main() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(
        "proxy.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()