"""
Reverse proxy entrypoint.

Local:  python app.py
PythonAnywhere WSGI: from app import app as application
"""

from a2wsgi import ASGIMiddleware

from proxy.app import create_app, main

_starlette = create_app()
app = ASGIMiddleware(_starlette)
application = app

if __name__ == "__main__":
    main()