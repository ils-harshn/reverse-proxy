import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _optional(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    return value or default


def _optional_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    base_url: str
    host: str
    port: int
    public_url: str | None
    upstream_timeout: float
    # When True, upstream httpx calls use trust_env=False (ignore HTTP(S)_PROXY, etc.)
    ignore_env: bool

    @property
    def base_origin(self) -> str:
        """Scheme + netloc of BASE_URL (no path)."""
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def base_path_prefix(self) -> str:
        """Path prefix on upstream (e.g. /api), normalized without trailing slash."""
        parsed = urlparse(self.base_url)
        path = parsed.path.rstrip("/")
        return path if path else ""


def load_settings() -> Settings:
    base_url = _require("BASE_URL").rstrip("/")
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("BASE_URL must be a full URL, e.g. https://example.com")

    public = os.getenv("PUBLIC_URL", "").strip() or None
    if public:
        public = public.rstrip("/")
        pub = urlparse(public)
        if not pub.scheme or not pub.netloc:
            raise ValueError("PUBLIC_URL must be a full URL when set")

    return Settings(
        base_url=base_url,
        host=_optional("HOST", "0.0.0.0"),
        port=int(_optional("PORT", "8080")),
        public_url=public,
        upstream_timeout=float(_optional("UPSTREAM_TIMEOUT", "60")),
        ignore_env=_optional_bool("IGNORE_ENV", True),
    )