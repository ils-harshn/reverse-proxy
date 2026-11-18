from urllib.parse import urlparse

from proxy.config import Settings


def build_upstream_url(settings: Settings, path: str, query_string: str = "") -> str:
    parsed = urlparse(settings.base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    prefix = parsed.path.rstrip("/")
    if path == "/":
        upstream_path = prefix or "/"
    else:
        upstream_path = f"{prefix}{path}" if prefix else path
    query = f"?{query_string}" if query_string else ""
    return f"{origin}{upstream_path}{query}"