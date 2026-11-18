"""
Reverse proxy entrypoint.

Local (async / uvicorn):  python app.py
PythonAnywhere WSGI:      from app import app as application
"""

from proxy.wsgi_app import application as app

application = app

if __name__ == "__main__":
    from proxy.app import main

    main()