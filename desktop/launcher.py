from __future__ import annotations

import os
import socket
import threading
import time

import uvicorn
import webview

from backend.app import app
from backend.config import settings


def run_backend() -> None:
    uvicorn.run(
        app,
        host=settings.backend_host,
        port=settings.backend_port,
        log_level="info" if settings.debug else "warning",
    )


def wait_for_backend(timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((settings.backend_host, settings.backend_port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError("FastAPI backend did not become ready in time.")


def main() -> None:
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    wait_for_backend()
    url = f"http://{settings.backend_host}:{settings.backend_port}/"
    if os.getenv("DEPOPRO_LAUNCHER_SMOKE_TEST") == "1":
        return
    webview.create_window(
        title=settings.app_name,
        url=url,
        width=1600,
        height=1000,
        min_size=(1200, 780),
    )
    webview.start(debug=settings.debug)


if __name__ == "__main__":
    main()
