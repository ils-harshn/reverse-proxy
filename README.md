# Python reverse proxy

Forwards all HTTP requests to `BASE_URL` from `.env`, streams responses, and rewrites redirect `Location` headers when `PUBLIC_URL` is set.

## Setup (run manually)

From the project root (`reverseProxyServer`):

```powershell
cd D:\Public\Local\AI\reverseProxyServer
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create your environment file:

```powershell
copy .env.example .env
```

Edit `.env` and set at least `BASE_URL`, for example:

```env
BASE_URL=https://httpbin.org
HOST=0.0.0.0
PORT=8080
PUBLIC_URL=http://localhost:8080
```

## Run

```powershell
python app.py
```

`HOST` and `PORT` come from `.env`.

## Test

Health check (not proxied to upstream):

```powershell
curl http://localhost:8080/_proxy/health
```

Proxy a path (example with httpbin):

```powershell
curl http://localhost:8080/get
```

Redirect rewrite: if upstream returns `Location: https://upstream/...`, clients see `Location: http://localhost:8080/...` when `PUBLIC_URL` is set.

## PythonAnywhere

1. Upload the project to e.g. `/home/reverseproxy/reverse-proxy`.
2. In a **Bash console** (with venv if you use one): `pip install -r requirements.txt`.
3. Edit `.env`: `BASE_URL`, `PUBLIC_URL=https://reverseproxy.pythonanywhere.com`, `IGNORE_ENV=true`.
4. **Web** → WSGI file: add project to `sys.path` and `from app import app as application` (see below).
5. **Reload** the web app.

### WSGI configuration file example

```python
import sys

project_home = "/home/reverseproxy/reverse-proxy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application  # noqa
```

`IGNORE_ENV=true` makes httpx use `trust_env=False` so outbound calls to `BASE_URL` are not sent through PythonAnywhere’s `HTTP(S)_PROXY` environment variables.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `BASE_URL` | Yes | Upstream origin, optionally with path prefix (`https://api.example.com/v1`) |
| `PUBLIC_URL` | Recommended | Client-facing URL for redirect rewriting |
| `IGNORE_ENV` | No | Default `true`; ignore proxy env when requesting upstream (`httpx` `trust_env=False`) |
| `HOST` | No | Local uvicorn bind (default `127.0.0.1`) |
| `PORT` | No | Local uvicorn port (default `8080`) |
| `UPSTREAM_TIMEOUT` | No | Seconds (default `60`) |