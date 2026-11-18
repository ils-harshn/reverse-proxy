from urllib.parse import urljoin, urlparse

import httpx

# RFC 7230 hop-by-hop headers; do not forward these
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def filter_request_headers(headers: list[tuple[bytes, bytes]], upstream_host: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_name, raw_value in headers:
        name = raw_name.decode("latin-1").lower()
        if name in HOP_BY_HOP:
            continue
        value = raw_value.decode("latin-1")
        if name == "host":
            out["Host"] = upstream_host
            continue
        # Let httpx set content-length for streamed bodies when appropriate
        canonical = "-".join(part.capitalize() for part in name.split("-"))
        out[canonical] = value
    if "Host" not in out:
        out["Host"] = upstream_host
    return out


def filter_response_headers(headers: httpx.Headers) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for name, value in headers.multi_items():
        if name.lower() in HOP_BY_HOP:
            continue
        result.append((name, value))
    return result


def rewrite_location(location: str, base_origin: str, public_url: str | None) -> str:
    if not public_url:
        return location
    parsed = urlparse(location)
    if parsed.scheme and parsed.netloc:
        if location.startswith(base_origin):
            return public_url + location[len(base_origin) :]
        return location
    if location.startswith("/"):
        pub = urlparse(public_url)
        return f"{pub.scheme}://{pub.netloc}{location}"
    return urljoin(base_origin + "/", location)